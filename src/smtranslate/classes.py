from dataclasses import dataclass


@dataclass
class Translation:
    langid: str
    translation: str
    param_count: int


@dataclass
class Phrase:
    key: str
    format: Translation | None
    translations: list[Translation]


@dataclass
class PhraseFile:
    filename: str
    phrases: list[Phrase]
    error: str | None = None


@dataclass
class Language:
    langid: str
    name: str
    files: list[PhraseFile]


@dataclass
class Report:
    langid: str
    filename: str
    file_warning: str = ""
    phrase_key: str = ""
    phrase_warning: str = ""
