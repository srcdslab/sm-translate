#!/usr/bin/python3
# Copyright (c) 2023 Peace-Maker
from collections import defaultdict
import logging
import pathlib
import re
import vdf

from smtranslate.classes import Language, Phrase, PhraseFile, Report, Translation

logger = logging.getLogger(__name__)


def parse_translations(path: str):
    param_regex = re.compile(r"\{[0-9]+\}", re.MULTILINE)
    units = []
    for file in pathlib.Path(path).glob("*.txt"):
        logger.debug(f"Parsing {file}")
        if not file.is_file():
            continue

        try:
            phrases = vdf.loads(file.read_text("utf-8"))
        except Exception as ex:
            file_path = str(file)
            index = file_path.find("translations")
            if index != -1:
                file_path = file_path[index:]
            logger.error(f"Error parsing {file_path}: {ex}")
            units.append(PhraseFile(file.name, [], str(ex)))
            continue

        if "Phrases" not in phrases:
            logger.error(f'File {file.name} does not start with a "Phrases" section')
            continue

        parsed_phrases = []
        for phrase_ident, raw_translations in phrases["Phrases"].items():
            translations = []
            format_special = None
            for child_langid, translation in raw_translations.items():
                if child_langid == "#format":
                    format_special = Translation(
                        child_langid, translation, translation.count(",") + 1
                    )
                else:
                    translations.append(
                        Translation(
                            child_langid,
                            translation,
                            len(param_regex.findall(translation)),
                        )
                    )
            parsed_phrases.append(Phrase(phrase_ident, format_special, translations))
        units.append(PhraseFile(file.name, parsed_phrases))
    return units


def run(*, language_cfg_path: str, translation_folder_path: str) -> None:
    # Parse the languages.cfg file to know which languages could be available
    logger.info("Parsing languages.cfg...")
    available_languages: dict[str, Language] = {}
    languages_cfg = vdf.loads(pathlib.Path(language_cfg_path).read_text("utf-8"))
    for langid, lang in languages_cfg["Languages"].items():
        available_languages[langid] = Language(langid, lang, [])

    logger.info(f"Available languages: {len(available_languages)}")

    # Parse the english translation, since it doesn't use a subdirectory and is the baseline for all other translations
    available_languages["en"].files = parse_translations(translation_folder_path)

    # Parse the other translations
    for langid, lang in available_languages.items():
        if langid == "en":
            continue
        lang.files = parse_translations(f"{translation_folder_path}/{langid}")

    reports: dict[str, dict[str, list[Report]]] = defaultdict(lambda: defaultdict(list))

    # Compare the english translation with the other translations
    english = available_languages["en"]
    for langid, lang in available_languages.items():
        if langid == "en":
            continue

        # See if this language has anything that English doesn't
        for file in lang.files:
            english_file = next(
                (x for x in english.files if x.filename == file.filename), None
            )
            if english_file is None:
                reports[langid][file.filename].append(
                    Report(
                        langid,
                        file.filename,
                        file_warning="File doesn't exist in English",
                    )
                )
                continue

            if not file.phrases:
                reports[langid][file.filename].append(
                    Report(langid, file.filename, file_warning="File is empty")
                )
                continue

            for phrase in file.phrases:
                if phrase.format:
                    reports[langid][file.filename].append(
                        Report(
                            langid,
                            file.filename,
                            phrase_key=phrase.key,
                            phrase_warning='Includes a "#format" key',
                        )
                    )
                english_phrase = next(
                    (x for x in english_file.phrases if x.key == phrase.key), None
                )
                if english_phrase is None:
                    # look for this phrase in a different english file
                    warning = "Phrase doesn't exist in English"
                    for other_file in english.files:
                        other_phrase = next(
                            (x for x in other_file.phrases if x.key == phrase.key), None
                        )
                        if other_phrase:
                            warning = f"Phrase exists in a different file in English: {other_file.filename}"
                            break
                    reports[langid][file.filename].append(
                        Report(
                            langid,
                            file.filename,
                            phrase_key=phrase.key,
                            phrase_warning=warning,
                        )
                    )
                    continue
                translation_found = False
                for translation in phrase.translations:
                    if translation.langid == langid:
                        translation_found = True
                    else:
                        reports[langid][file.filename].append(
                            Report(
                                langid,
                                file.filename,
                                phrase_key=phrase.key,
                                phrase_warning=f'Includes a translation for language "{translation.langid}"',
                            )
                        )
                    if (
                        english_phrase.format
                        and translation.param_count != english_phrase.format.param_count
                    ):
                        reports[langid][file.filename].append(
                            Report(
                                langid,
                                file.filename,
                                phrase_key=phrase.key,
                                phrase_warning=f"Has {translation.param_count} format parameters, but English has {english_phrase.format.param_count}",
                            )
                        )
                if not translation_found:
                    reports[langid][file.filename].append(
                        Report(
                            langid,
                            file.filename,
                            phrase_key=phrase.key,
                            phrase_warning="Phrase available, but translation missing",
                        )
                    )

        # See if this language is missing anything that English has
        for file in english.files:
            lang_file = next(
                (x for x in lang.files if x.filename == file.filename), None
            )
            if lang_file is None:
                reports[langid][file.filename].append(
                    Report(langid, file.filename, file_warning="File missing")
                )
                continue

            # The file doesn't contain any phrases. We reported that already, so don't spam every single missing phrase
            if not lang_file.phrases:
                continue

            for phrase in file.phrases:
                lang_phrase = next(
                    (x for x in lang_file.phrases if x.key == phrase.key), None
                )
                if lang_phrase is None:
                    reports[langid][file.filename].append(
                        Report(
                            langid,
                            file.filename,
                            phrase_key=phrase.key,
                            phrase_warning="Phrase missing",
                        )
                    )

        if langid not in reports:
            logger.info(f"No issues found for {lang.name} ({langid})")
        else:
            logger.error(
                f"Found {len(reports[langid])} issues for {lang.name} ({langid})"
            )

    # Generate the report markdown for the project draft issues
    for langid, lang in available_languages.items():
        markdown = ""

        if langid in reports:
            print(f"Generating report for {lang.name} ({langid})...")
            for filename, problems in reports[langid].items():
                markdown += f"## [{filename}](https://github.com/alliedmodders/sourcemod/blob/master/translations/{langid}/{filename})\n"
                added_phrase_warning = False
                for report in problems:
                    if report.file_warning:
                        markdown += f"**{report.file_warning}**\n"
                        print(f"  {report.file_warning} ({report.filename})")
                    if report.phrase_warning:
                        if not added_phrase_warning:
                            markdown += "| Phrase | Issue |\n| ------- | --------- |\n"
                            added_phrase_warning = True
                        markdown += (
                            f"| `{report.phrase_key}` | {report.phrase_warning} |\n"
                        )
                        print(
                            f'  {report.filename}: "{report.phrase_key}" -> {report.phrase_warning}'
                        )
                markdown += "\n"
        else:
            markdown = "No issues found"
