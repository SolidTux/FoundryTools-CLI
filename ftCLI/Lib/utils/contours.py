import itertools
from typing import Callable, Iterable, Optional, Mapping

import pathops
from fontTools.cffLib import CharStrings
from fontTools.misc.roundTools import otRound
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import ttFont
from fontTools.ttLib.tables import _g_l_y_f
from fontTools.ttLib.tables import _h_m_t_x

from ftCLI.Lib.Font import Font
from ftCLI.Lib.utils.click_tools import generic_error_message, generic_warning_message


def fix_cff_charstrings(font: Font):
    fixed_charstrings = {}
    glyph_set = font.getGlyphSet()

    top_dict = font['CFF '].cff.topDictIndex[0]
    private = top_dict.Private
    charset = top_dict.charset
    global_subrs = top_dict.GlobalSubrs

    charstrings = CharStrings(
        None, charset=charset, globalSubrs=global_subrs, private=private, fdSelect=None, fdArray=None
    )

    for k, v in glyph_set.items():
        pathops_path = pathops.Path()
        pathops_pen = pathops_path.getPen(glyphSet=glyph_set)
        try:
            glyph_set[k].draw(pathops_pen)
            pathops_path.simplify()
            t2_pen = T2CharStringPen(v.width, glyphSet=glyph_set)
            pathops_path.draw(t2_pen)
            fixed_charstring = t2_pen.getCharString()
            fixed_charstrings[k] = fixed_charstring
        except Exception as e:
            generic_error_message(e)

        for glyph_name, charstring in fixed_charstrings.items():
            charstring.private = private
            charstring.globalSubrs = global_subrs,
            charstrings[glyph_name] = charstring
        top_dict.CharStrings = charstrings


# The following code is adapted from fontTools.ttLib.removeOverlaps
class RemoveOverlapsError(Exception):
    pass


_TTGlyphMapping = Mapping[str, ttFont._TTGlyph]


def skPathFromGlyph(glyphName: str, glyphSet: _TTGlyphMapping) -> pathops.Path:
    path = pathops.Path()
    pathPen = path.getPen(glyphSet=glyphSet)
    glyphSet[glyphName].draw(pathPen)
    return path


def skPathFromGlyphComponent(
    component: _g_l_y_f.GlyphComponent, glyphSet: _TTGlyphMapping
):
    baseGlyphName, transformation = component.getComponentInfo()
    path = skPathFromGlyph(baseGlyphName, glyphSet)
    return path.transform(*transformation)


def componentsOverlap(glyph: _g_l_y_f.Glyph, glyphSet: _TTGlyphMapping) -> bool:
    if not glyph.isComposite():
        raise ValueError("This method only works with TrueType composite glyphs")
    if len(glyph.components) < 2:
        return False  # single component, no overlaps

    component_paths = {}

    def _get_nth_component_path(index: int) -> pathops.Path:
        if index not in component_paths:
            component_paths[index] = skPathFromGlyphComponent(
                glyph.components[index], glyphSet
            )
        return component_paths[index]

    return any(
        pathops.op(
            _get_nth_component_path(i),
            _get_nth_component_path(j),
            pathops.PathOp.INTERSECTION,
            fix_winding=True,
            keep_starting_points=False,
        )
        for i, j in itertools.combinations(range(len(glyph.components)), 2)
    )


def ttfGlyphFromSkPath(path: pathops.Path) -> _g_l_y_f.Glyph:
    # Skia paths have no 'components', no need for glyphSet
    ttPen = TTGlyphPen(glyphSet=None)
    path.draw(ttPen)
    glyph = ttPen.glyph()
    assert not glyph.isComposite()
    # compute glyph.xMin (glyfTable parameter unused for non composites)
    glyph.recalcBounds(glyfTable=None)
    return glyph


def _round_path(path: pathops.Path, round: Callable[[float], float] = otRound) -> pathops.Path:
    rounded_path = pathops.Path()
    for verb, points in path:
        rounded_path.add(verb, *((round(p[0]), round(p[1])) for p in points))
    return rounded_path


def _simplify(path: pathops.Path, debugGlyphName: str) -> pathops.Path:
    # skia-pathops has a bug where it sometimes fails to simplify paths when there
    # are float coordinates and control points are very close to one another.
    # Rounding coordinates to integers works around the bug.
    # Since we are going to round glyf coordinates later on anyway, here it is
    # ok(-ish) to also round before simplify. Better than failing the whole process
    # for the entire font.
    # https://bugs.chromium.org/p/skia/issues/detail?id=11958
    # https://github.com/google/fonts/issues/3365

    try:
        # set clockwise to True to fix winding
        return pathops.simplify(path, clockwise=True)
    except pathops.PathOpsError:
        pass

    path = _round_path(path)
    try:
        # set clockwise to True to fix winding
        path = pathops.simplify(path, clockwise=True)
        generic_warning_message(
            f"skia-pathops failed to simplify {debugGlyphName} with float coordinates, but succeded using rounded "
            f"integer coordinates "
        )
        return path
    except pathops.PathOpsError as e:
        generic_error_message(f"Failed to remove overlaps from glyph {debugGlyphName!r}: {e}")

    raise AssertionError("Unreachable")


def removeTTGlyphOverlaps(
    glyphName: str,
    glyphSet: _TTGlyphMapping,
    glyfTable: _g_l_y_f.table__g_l_y_f,
    hmtxTable: _h_m_t_x.table__h_m_t_x,
    removeHinting: bool = True,
) -> bool:
    glyph = glyfTable[glyphName]
    # decompose composite glyphs only if components overlap each other
    if (
        glyph.numberOfContours > 0
        or glyph.isComposite()
        and componentsOverlap(glyph, glyphSet)
    ):
        path = skPathFromGlyph(glyphName, glyphSet)

        # remove overlaps
        path2 = _simplify(path, glyphName)

        # replace TTGlyph if simplified path is different (ignoring contour order)
        if {tuple(c) for c in path.contours} != {tuple(c) for c in path2.contours}:
            glyfTable[glyphName] = glyph = ttfGlyphFromSkPath(path2)
            # simplified glyph is always unhinted
            assert not glyph.program
            # also ensure hmtx LSB == glyph.xMin so glyph origin is at x=0
            width, lsb = hmtxTable[glyphName]
            if lsb != glyph.xMin:
                hmtxTable[glyphName] = (width, glyph.xMin)
            return True

    if removeHinting:
        glyph.removeHinting()
    return False


def fix_true_type_contours(
    font: ttFont.TTFont,
    glyphNames: Optional[Iterable[str]] = None,
    removeHinting: bool = True,
    ignoreErrors=False,
) -> None:

    try:
        glyfTable = font["glyf"]
    except KeyError:
        raise NotImplementedError("fix_true_type_contours currently only works with TTFs")

    hmtxTable = font["hmtx"]
    # wraps the underlying glyf Glyphs, takes care of interfacing with drawing pens
    glyphSet = font.getGlyphSet()

    if glyphNames is None:
        glyphNames = font.getGlyphOrder()

    # process all simple glyphs first, then composites with increasing component depth,
    # so that by the time we test for component intersections the respective base glyphs
    # have already been simplified
    glyphNames = sorted(
        glyphNames,
        key=lambda name: (
            glyfTable[name].getCompositeMaxpValues(glyfTable).maxComponentDepth
            if glyfTable[name].isComposite()
            else 0,
            name,
        ),
    )
    modified = set()
    for glyphName in glyphNames:
        try:
            if removeTTGlyphOverlaps(
                glyphName, glyphSet, glyfTable, hmtxTable, removeHinting
            ):
                modified.add(glyphName)
        except RemoveOverlapsError:
            if not ignoreErrors:
                raise
            generic_error_message(f"Failed to remove overlaps for {glyphName}")



