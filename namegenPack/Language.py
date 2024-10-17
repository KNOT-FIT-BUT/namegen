# -*- coding: UTF-8 -*-
""""
Created on 04.09.20
Modul pro práci s jazykem.

:author:     Martin Dočekal
"""
import ast
import os
from typing import Optional, Set

from namegenPack.Errors import ExceptionMessageCode, ErrorMessenger
from namegenPack.Grammar import Grammar, Lex, InvalidGrammarException
from namegenPack.morpho.MorphoAnalyzer import MorphoAnalyzerLibma


class Language(object):
    """
    Načítá struktury pro práci s daným jazykem.

    :ivar code: kód jazyka (cs)
    :vartype code: str
    :ivar gTimeout: timeout pro gramatiky
    :vartype gTimeout: int
    :ivar gFemale: gramatika pro ženy
    :vartype gFemale: Grammar
    :ivar gMale:  gramatika pro muže
    :vartype gMale: Grammar
    :ivar gLocations: gramatika pro lokace
    :vartype gLocations: Grammar
    :ivar gEvents: gramatika pro události
    :vartype gEvents: Grammar
    :ivar titles: množina titulů
    :vartype titles: Set[str]
    :ivar eqGen:
            Definuje množiny slov, která jsou ekvivalentní a mají se rozgenerovat všechna
            ostatní z dané množiny pokud je na vstupu jedno z nich.
            Uveďte název python souboru.
    :vartype eqGen: str
    :ivar lex: lexikální analyzátor pro tento jazyk
    :vartype lex: Lex
    """

    def __init__(self, langFolder: str, gFemale: str, gMale: str, gLocations: str, gEvents: str, titles: str, eqGen: str,
                 ma: str,
                 gTimeout: Optional[int]):
        """
        Načte jazyk z jeho složky.

        :param langFolder: Cesta ke složce s jazykem.
        :type langFolder: str
        :param gFemale: Nazev soubor s gramatikou pro ženy.
        :type gFemale: str
        :param gMale: Název souboru s gramatikou pro muže.
        :type gMale: str
        :param gLocations: Název souboru s gramatikou pro lokace.
        :type gLocations: str
        :param gEvents: Název souboru s gramatikou pro události.
        :type gEvents: str
        :param titles: Název souboru s tituly.
        :type titles: str
        :param eqGen:
            Definuje množiny slov, která jsou ekvivalentní a mají se rozgenerovat všechna
            ostatní z dané množiny pokud je na vstupu jedno z nich.
            Uveďte název python souboru.
        :type eqGen: str
        :param ma: Název skriptu pro morfologický analyzátor.
        :type ma: str
        :param gTimeout: Timeout pro gramatiky.
        :type gTimeout: Optional[int]
        """

        self.code = os.path.split(langFolder)[-1]
        self.gTimeout = gTimeout

        grammarsPath = os.path.join(langFolder, "grammars")

        grammar = "female"  # just to mark which grammar is problematic
        try:
            self.gFemale = Grammar(os.path.join(grammarsPath, gFemale), gTimeout)
            grammar = "male"
            self.gMale = Grammar(os.path.join(grammarsPath, gMale), gTimeout)
            grammar = "locations"
            self.gLocations = Grammar(os.path.join(grammarsPath, gLocations), gTimeout)
            grammar = "events"
            self.gEvents = Grammar(os.path.join(grammarsPath, gEvents), gTimeout)

        except InvalidGrammarException as e:
            e.message = "\n" + grammar + "\n" + e.message
            raise e

        self.titles = self._readTitles(os.path.join(langFolder, titles))



        with open(os.path.join(langFolder, eqGen), "r") as f:
            self.eqGen = ast.literal_eval(f.read())

        self.lex = Lex(self.titles)
        self._maPath = os.path.join(langFolder, ma)

        self._ma = None

    @property
    def ma(self) -> MorphoAnalyzerLibma:
        """
        Morfologický analyzátor.

        :raise ExceptionMessageCode: Musí být inicializován pomocí :func:`~Language.Language.initMAnalyzer` jinak
        exception.
        """
        
        if self._ma is None:
            raise ExceptionMessageCode(ErrorMessenger.CODE_LANGUAGE_NOT_INIT_MA)
        return self._ma

    def initMAnalyzer(self, words: Set[str]):
        """
        Provede inicializaci morfologického analyzátoru pomocí daných slov.

        :param words: Slova pro inicializaci
        """

        self._ma = MorphoAnalyzerLibma(self._maPath, words)

    @staticmethod
    def _readTitles(pathT) -> Set[str]:
        """
        Získá tituly ze souboru s tituly.

        :param pathT: Cesta k souboru
        :type pathT: str
        :return: Množina se všemi tituly.
        :rtype: Set[str]
        """
        titles = set()
        with open(pathT, "r") as titlesF:
            for line in titlesF:
                content = line.split("#", 1)[0].strip()
                if content:
                    for t in content.split():
                        titles.add(t)

        return titles



