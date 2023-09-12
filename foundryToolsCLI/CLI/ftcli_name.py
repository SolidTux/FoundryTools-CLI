from copy import deepcopy
from pathlib import Path

import click
from fontTools.misc.cliTools import makeOutputFileName

from foundryToolsCLI.Lib.constants import LANGUAGES_EPILOG
from foundryToolsCLI.Lib.tables.name import TableName
from foundryToolsCLI.Lib.utils.cli_tools import get_fonts_in_path, get_output_dir, initial_check_pass
from foundryToolsCLI.Lib.utils.click_tools import (
    add_file_or_path_argument,
    add_common_options,
    file_saved_message,
    file_not_changed_message,
    generic_error_message,
)

tbl_name = click.Group("subcommands")


@tbl_name.command(epilog=LANGUAGES_EPILOG)
@add_file_or_path_argument()
@click.option(
    "-n",
    "--name-id",
    type=click.IntRange(0, 32767),
    required=True,
    help="nameID of the NameRecord to add.",
)
@click.option("-s", "--string", required=True, help="The string to write in the NameRecord.")
@click.option(
    "-p",
    "--platform-id",
    type=click.Choice(choices=["1", "3"]),
    help="""
    platformID of the NameRecord to add (1: Macintosh, 3: Windows).
    
    If platformID is not specified, both a platformID=1 and a platformID=3 NameRecords will be added.
    """,
)
@click.option(
    "-l",
    "--language-string",
    default="en",
    show_default=True,
    help="""
    Write the NameRecord in a language different than English (e.g.: 'it', 'nl', 'de').

    See epilog for a list of valid language strings.
    """,
)
@add_common_options()
def set_name(
    input_path: Path,
    name_id: int,
    platform_id: int,
    string: str,
    language_string: str,
    recalc_timestamp: bool = False,
    output_dir: Path = None,
    overwrite: bool = True,
) -> None:
    """
    Writes a NameRecord in the 'name' table.
    """

    fonts = get_fonts_in_path(input_path=input_path, recalc_timestamp=recalc_timestamp)
    output_dir = get_output_dir(input_path=input_path, output_dir=output_dir)
    if not initial_check_pass(fonts=fonts, output_dir=output_dir):
        return

    if platform_id:
        platform_id = int(platform_id)

    for font in fonts:
        try:
            name_table: TableName = font["name"]
            name_table_copy = deepcopy(name_table)

            name_table.add_name(
                font,
                name_id=name_id,
                string=string,
                platform_id=platform_id,
                language_string=language_string,
            )

            file = Path(font.reader.file.name)
            if name_table_copy.compile(font) != name_table.compile(font):
                output_file = Path(makeOutputFileName(file, outputDir=output_dir, overWrite=overwrite))
                font.save(output_file)
                file_saved_message(output_file)
            else:
                file_not_changed_message(file)

        except Exception as e:
            generic_error_message(e)
        finally:
            font.close()


@tbl_name.command(epilog=LANGUAGES_EPILOG)
@add_file_or_path_argument()
@click.option(
    "-n",
    "--name-id",
    "name_ids",
    type=click.IntRange(0, 32767, max_open=True),
    required=True,
    multiple=True,
    help="""
    nameID of the NameRecord to delete.

    This option can be repeated to delete multiple NameRecords at once (e.g.: -x 3 -x 5 -x 6).
    """,
)
@click.option(
    "-p",
    "--platform-id",
    type=click.Choice(choices=["0", "1", "3"]),
    help="""
    If platformID is specified, only NameRecords with matching platformID will be deleted.

    Valid platformID values are: 0 (Unicode), 1 (Macintosh), 3 (Windows).
    """,
)
@click.option(
    "-l",
    "--language-string",
    default=None,
    show_default=True,
    help="""
    Filter the NameRecords to delete by language string (for example: 'it', 'de', 'nl').

    See epilog for a list of valid language strings.
    """,
)
@add_common_options()
def del_names(
    input_path: Path,
    name_ids: tuple[int],
    platform_id: int,
    language_string: str,
    recalc_timestamp: bool = False,
    output_dir: Path = None,
    overwrite: bool = True,
):
    """
    Deletes one or more NameRecords.
    """

    fonts = get_fonts_in_path(input_path, recalc_timestamp=recalc_timestamp)
    output_dir = get_output_dir(input_path=input_path, output_dir=output_dir)
    if not initial_check_pass(fonts=fonts, output_dir=output_dir):
        return

    if platform_id:
        platform_id = int(platform_id)

    for font in fonts:
        try:
            name_table: TableName = font["name"]
            name_table_copy = deepcopy(name_table)

            name_table.del_names(
                name_ids=name_ids,
                platform_id=platform_id,
                language_string=language_string,
            )

            file = Path(font.reader.file.name)
            if name_table_copy.compile(font) != name_table.compile(font):
                output_file = Path(makeOutputFileName(file, outputDir=output_dir, overWrite=overwrite))
                font.save(output_file)
                file_saved_message(output_file)
            else:
                file_not_changed_message(file)

        except Exception as e:
            generic_error_message(e)
        finally:
            font.close()


@tbl_name.command()
@add_file_or_path_argument()
@click.option("-os", "--old-string", required=True, help="The string to be replaced")
@click.option("-ns", "--new-string", required=True, help="The string to replace the old string with")
@click.option(
    "-n",
    "--name-id",
    "name_ids",
    type=click.IntRange(0, 32767, max_open=True),
    multiple=True,
    help="""
    nameID of the NameRecords where to search and replace the string.

    If nameID is not specified, the string will be replaced in all NameRecords.

    This option can be repeated (e.g.: -x 3 -x 5 -x 6).
    """,
)
@click.option(
    "-x",
    "--exclude-name-id",
    "excluded_name_ids",
    type=click.IntRange(0, 32767, max_open=True),
    multiple=True,
    help="""
    nameID of the NameRecords to skip.

    This option can be repeated (e.g.: -x 3 -x 5 -x 6).
    """,
)
@click.option(
    "-p",
    "--platform-id",
    type=click.Choice(choices=["0", "1", "3"]),
    help="""
    platformID of the NameRecords where to perform find and replace (0: Unicode, 1: Macintosh, 3: Windows).
    """,
)
@add_common_options()
def find_replace(
    input_path: Path,
    old_string: str,
    new_string: str,
    name_ids: tuple[int],
    excluded_name_ids: tuple[int],
    platform_id: int,
    recalc_timestamp: bool = False,
    output_dir: Path = None,
    overwrite: bool = True,
):
    """
    Finds a string in the specified NameRecords and replaces it with a new string
    """

    fonts = get_fonts_in_path(input_path=input_path, recalc_timestamp=recalc_timestamp)
    output_dir = get_output_dir(input_path=input_path, output_dir=output_dir)
    if not initial_check_pass(fonts=fonts, output_dir=output_dir):
        return

    if platform_id:
        platform_id = int(platform_id)

    for font in fonts:
        try:
            name_table: TableName = font["name"]
            name_table_copy = deepcopy(name_table)

            name_table.find_replace(
                old_string=old_string,
                new_string=new_string,
                name_ids_to_include=name_ids,
                name_ids_to_skip=excluded_name_ids,
                platform_id=platform_id,
            )

            file = Path(font.reader.file.name)
            if name_table_copy.compile(font) != name_table.compile(font):
                output_file = Path(makeOutputFileName(file, outputDir=output_dir, overWrite=overwrite))
                font.save(output_file)
                file_saved_message(output_file)
            else:
                file_not_changed_message(file)

        except Exception as e:
            generic_error_message(e)
        finally:
            font.close()


@tbl_name.command()
@add_file_or_path_argument()
@click.option("--del-all", is_flag=True, help="Deletes also nameIDs 1, 2, 4, 5 and 6.")
@add_common_options()
def del_mac_names(
    input_path: Path,
    del_all: bool = False,
    recalc_timestamp: bool = False,
    output_dir: bool = None,
    overwrite: bool = True,
):
    """
    Deletes all the Macintosh NameRecords (platformID=1) from the name table, except the ones with nameID 1, 2, 4, 5,
    and 6.

    According to Apple (https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6name.html), "names with
    platformID 1 were required by earlier versions of macOS. Its use on modern platforms is discouraged. Use names with
    platformID 3 instead for maximum compatibility. Some legacy software, however, may still require names with
    platformID 1, platformSpecificID 0".
    """

    fonts = get_fonts_in_path(input_path, recalc_timestamp=recalc_timestamp)
    output_dir = get_output_dir(input_path=input_path, output_dir=output_dir)
    if not initial_check_pass(fonts=fonts, output_dir=output_dir):
        return

    for font in fonts:
        try:
            name_table: TableName = font["name"]
            name_table_copy = deepcopy(name_table)
            name_ids = set(name.nameID for name in name_table.names if name.platformID == 1)
            if not del_all:
                for n in (1, 2, 4, 5, 6):
                    try:
                        name_ids.remove(n)
                    except KeyError:
                        pass

            name_table.del_names(name_ids=name_ids, platform_id=1)

            file = Path(font.reader.file.name)
            if name_table_copy.compile(font) != name_table.compile(font):
                output_file = Path(makeOutputFileName(file, outputDir=output_dir, overWrite=overwrite))
                font.save(output_file)
                file_saved_message(output_file)
            else:
                file_not_changed_message(file)

        except Exception as e:
            generic_error_message(e)
        finally:
            font.close()


@tbl_name.command(epilog=LANGUAGES_EPILOG)
@add_file_or_path_argument()
@click.option(
    "-n",
    "--name-id",
    "name_ids",
    required=True,
    multiple=True,
    type=int,
    help="""
    nameID of the NameRecords where to append the prefix/suffix.

    This option can be repeated to prepend/append the string to multiple NameRecords (e.g.: -x 3 -x 5 -x 6).
    """,
)
@click.option(
    "-p",
    "--platform-id",
    type=click.Choice(choices=["0", "1", "3"]),
    help="""
    Use this option to add the prefix/suffix only to the NameRecords matching the provided platformID (0: Unicode, 1:
    Macintosh, 3: Windows).
    """,
)
@click.option(
    "-l",
    "--language-string",
    help="""
    Use this option to append the prefix/suffix only to the NameRecords matching the provided language string.
    
    See epilog for a list of valid language strings.
    """,
)
@click.option("--prefix", type=str, help="The string to be prepended to the NameRecords")
@click.option("--suffix", type=str, help="The suffix to append to the NameRecords")
@add_common_options()
def append(
    input_path: Path,
    name_ids: tuple[int],
    platform_id: int,
    language_string: str,
    prefix: str,
    suffix: str,
    recalc_timestamp: bool = False,
    output_dir: Path = None,
    overwrite: bool = True,
):
    """
    Appends a prefix and/or a suffix to the specified NameRecords.
    """

    if prefix is None and suffix is None:
        generic_error_message("Please, insert at least a prefix or a suffix to append")
        return

    fonts = get_fonts_in_path(input_path, recalc_timestamp=recalc_timestamp)
    output_dir = get_output_dir(input_path=input_path, output_dir=output_dir)
    if not initial_check_pass(fonts=fonts, output_dir=output_dir):
        return

    if platform_id:
        platform_id = int(platform_id)

    for font in fonts:
        try:
            name_table: TableName = font["name"]
            name_table_copy = deepcopy(name_table)

            name_table.append_string(
                name_ids=name_ids,
                platform_id=platform_id,
                language_string=language_string,
                prefix=prefix,
                suffix=suffix,
            )
            file = Path(font.reader.file.name)
            if name_table.compile(font) != name_table_copy.compile(font):
                output_file = Path(makeOutputFileName(file, outputDir=output_dir, overWrite=overwrite))
                font.save(output_file)
                file_saved_message(output_file)
            else:
                file_not_changed_message(file)

        except Exception as e:
            generic_error_message(e)
        finally:
            font.close()


cli = click.CommandCollection(
    sources=[tbl_name],
    help="""
    A set of tools to manipulate the 'name' table.
    """,
)
