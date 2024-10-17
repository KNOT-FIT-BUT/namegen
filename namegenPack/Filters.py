"""
Created on 24. 5. 2019
Modul se třídami (funktory) pro filtrování jmen.

:author:     Martin Dočekal
:contact:    xdocek09@stud.fit.vubtr.cz
"""

from abc import ABC, abstractmethod
from typing import Any, Set, Pattern

import unicodedata


# noinspection PyUnusedLocal
import namegenPack


def alwaysTrue(*args: Any, **kwargs: Any):
    """
    Tato funkce vždy vrací true bez ohledu na argumenty.

    :param args: Volitelné argumenty, na které není brán ohled.
    :type args: Any
    :param kwargs:  Volitelné argumenty, na které není brán ohled.
    :type kwargs: Any
    :return: Vždy vrací true.
    :rtype: bool
    """

    return True


class Filter(ABC):
    """
    Základni funktor pro filtrování
    """

    @abstractmethod
    def __call__(self, o: Any) -> bool:
        """
        Volání filtru
        
        :param o: objekt pro filtrování
        :type o: Any
        :return: True pokud má být objekt o propuštěn filtrem. False pokud má být odfiltrován.
        :rtype: bool
        """
        pass


class NameLanguagesFilter(Filter):
    """
    Filtruje jména na základě vybraných jazyků.
    """

    def __init__(self, languages: Set[str]):
        """
        Inicializace filtru.
        
        :param languages: Povolené jazyky.
        :type languages: Set[str]
        """

        self._languages = languages

    def __call__(self, o) -> bool:
        """
        Volání filtru
        
        :param o: jméno pro filtrování
        :type o: Name
        :return: True pokud má být jméno o propuštěno filtrem. False pokud má být odfiltrováno.
        :rtype: bool
        """
        if o.language is None:
            return False

        return o.language.code in self._languages


class NameRegexFilter(Filter):
    """
    Filtruje jména dle podoby samotného jména.
    """

    def __init__(self, nameRegex: Pattern):
        """
        Inicializace filtru.
        
        :param nameRegex: Regulární výraz určující množinu všech povolených jmen.
        :type nameRegex: Pattern
        """

        self._nameRegex = nameRegex

    def __call__(self, o) -> bool:
        """
        Volání filtru
        
        :param o: jméno pro filtrování
        :type o: Name
        :return: True pokud má být jméno o propuštěno filtrem. False pokud má být odfiltrováno.
        :rtype: bool
        """

        return bool(self._nameRegex.match(str(o)))


class NameAlfaFilter(Filter):
    """
    Filtruje jména na základě povolených alfa znaků.
    Propouští pouze jména jejichž alfa znaky jsou v dané množině alfa znaků. Nehledí na jiné druhy znaků.
    """

    def __init__(self, alfas: Set[str], caseInsensitive: bool = True):
        """
        Inicializace filtru.
        
        :param alfas: Povolené alfa znaky.
        :type alfas: Set[str]
        :param caseInsensitive: Defaultné nezaleží na velikosti písmen. Pokud je false, tak na velikosit
            písmen záleží.
        :type caseInsensitive: bool
        """

        self._alfas = alfas

        if caseInsensitive:
            self._alfas = set(c.upper() for c in self._alfas)

    def __call__(self, o) -> bool:
        """
        Volání filtru
        
        :param o: jméno pro filtrování
        :type o: Name
        :return: True pokud má být jméno o propuštěno filtrem. False pokud má být odfiltrováno.
        :rtype: bool
        """

        return all(not c.isalpha() or c.upper() in self._alfas for c in str(o))


class NameScriptFilter(Filter):
    """
    Filtruje jména na základě povoleného písma alfa znaků.
    Propouští pouze jména jejichž alfa znaky jsou v dané množině písma. Nehledí na jiné druhy znaků.
    Kontroluje výskyt poskytnutého řetězce ve výsledku unicodedata.name pro alpha znaky.
    """

    def __init__(self, script: str):
        """
        Inicializace filtru.
        
        :param script: Povolené písmo.
            Kontroluje výskyt poskytnutého řetězce ve výsledku unicodedata.name pro alpha znaky.
        :type script: str
        """

        self._script = script
        self._cache = {}

    def __call__(self, o) -> bool:
        """
        Volání filtru
        
        :param o: jméno pro filtrování
        :type o: Name
        :return: True pokud má být jméno o propuštěno filtrem. False pokud má být odfiltrováno.
        :rtype: bool
        """

        return all(self._inScript(c) for c in str(o))

    def _inScript(self, c):
        """
        Checks if given character is in script.
        
        :param c: Char
        :type c: str
        """
        try:
            return self._cache[c]
        except KeyError:
            res = not c.isalpha() or self._script in unicodedata.name(c, "")
            self._cache[c] = res
            return res


class NamesFilter(Filter):
    """
    Filtruje jména na základě vybraných jazyků a podoby samotného jména.
    """

    def __init__(self, languages: Set[str], nameRegex: Pattern, alfas: Set[str], script: str):
        """
        Inicializace filtru.
        
        :param languages: Povolené jazyky.
        :type languages: Set[str]
        :param nameRegex: Regulární výraz určující množinu všech povolených jmen.
        :type nameRegex: Pattern
        :param alfas: Povolené alfa znaky.
        :type alfas: Set[str]
        :param script: Povolené písmo.
            Kontroluje výskyt poskytnutého řetězce ve výsledku unicodedata.name pro alpha znaky.
        :type script: str
        """

        self._languages = alwaysTrue if languages is None else NameLanguagesFilter(languages)
        self._nameRegex = alwaysTrue if nameRegex is None else NameRegexFilter(nameRegex)
        self._alfaFilter = alwaysTrue if alfas is None else NameAlfaFilter(alfas)
        self._scriptFilter = alwaysTrue if script is None else NameScriptFilter(script)

    def __call__(self, o) -> bool:
        """
        Volání filtru
        
        :param o: jméno pro filtrování
        :type o: Name
        :return: True pokud má být jméno o propuštěno filtrem. False pokud má být odfiltrováno.
        :rtype: bool
        """

        return self._languages(o) and self._nameRegex(o) and self._alfaFilter(o) and self._scriptFilter(o)


class NamesGrammarFilter(Filter):
    """
    Filtruje jména na základě přislušnosti do jejich gramatiky.
    """

    def __init__(self, guessType: bool = True):
        """
        Inicializace filtru.

        :param guessType: True -> Použije odhad typu jména, před použitím gramatiky.
        :type guessType: bool
        """

        self._guessType = guessType

    def __call__(self, name) -> bool:
        tokens = name.language.lex.getTokens(name)

        try:
            # test if the name is in grammar's language

            tmpRes = name.guessType(tokens) if self._guessType else None
            _ = name.grammar.analyse(tokens)

            # jméno prošlo filtrem
            return True
        except namegenPack.Grammar.Grammar.NotInLanguage:
            # not in language
            return False
