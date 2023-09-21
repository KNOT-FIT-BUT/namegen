#!/usr/bin/env python3
# encoding: utf-8
"""
namegen -- Generátor tvarů jmen.

namegen je program pro generování tvarů jmen osob a lokací.

:author:     Martin Dočekal
:contact:    xdocek09@stud.fit.vubtr.cz
"""

import configparser
import csv
import os
import time
import traceback
from argparse import ArgumentParser
from collections import defaultdict
from functools import reduce
from typing import Any

import regex as re

import namegenPack.Grammar
import namegenPack.morpho.MorphCategories
import namegenPack.morpho.MorphoAnalyzer
from namegenPack import Grammar
from namegenPack.Filters import NamesFilter, NamesGrammarFilter
from namegenPack.Generators import GenerateAbbreFormOfPrep, GenerateNope, GenerateDerivatedForms, MultiGenerator
from namegenPack.Language import Language
from namegenPack.Name import *

outputFile = sys.stdout


class ConfigManagerInvalidException(Errors.ExceptionMessageCode):
    """
    Nevalidní konfigurace
    """
    pass


class ConfigManager(object):
    """
    Tato třída slouží pro načítání konfigurace z konfiguračního souboru.
    """

    sectionDefault = "DEFAULT"
    sectionFilters = "FILTERS"
    sectionDataFiles = "DATA_FILES"
    sectionGenerators = "GENERATORS"
    sectionGrammar = "GRAMMAR"

    def __init__(self):
        """
        Inicializace config manažéru.
        """

        self.configParser = configparser.ConfigParser()

    def read(self, filesPaths):
        """
        Přečte hodnoty z konfiguračních souborů. Také je validuje a převede do jejich datových typů.

        :param filesPaths: list s cestami ke konfiguračním souborům.
        :returns: Konfigurace.
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """
        try:
            self.configParser.read(filesPaths)
        except configparser.ParsingError as e:
            raise ConfigManagerInvalidException(Errors.ErrorMessenger.CODE_INVALID_CONFIG,
                                                "Nevalidní konfigurační soubor: " + str(e))

        return self.__transformVals()

    @staticmethod
    def getAbsolutePath(path):
        return ("{}/".format(os.path.dirname(os.path.abspath(__file__))) if path[:1] == '.' else "") + path

    def __transformVals(self) -> Dict[str, Dict[str, Any]]:
        """
        Převede hodnoty a validuje je.

        :returns: dict -- ve formátu jméno sekce jako klíč a k němu dict s hodnotami.
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """

        return {self.sectionDefault: self.__transformDefaults(), self.sectionFilters: self.__transformFilters(),
                self.sectionDataFiles: self.__transformDataFiles(),
                self.sectionGenerators: self.__transformGenerators(),
                self.sectionGrammar: self.__transformGrammar()}

    def __transformDefaults(self):
        """
        Převede hodnoty pro DEFAULT a validuje je.

        :returns: dict -- ve formátu jméno prametru jako klíč a k němu hodnota parametru
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """

        result = {
            "ALLOW_PRIORITY_FILTRATION":
                self.configParser[self.sectionDefault]["ALLOW_PRIORITY_FILTRATION"].lower() == "true"
        }

        # nastavení locale
        if self.configParser[self.sectionDefault]["LC_ALL"]:
            try:
                locale.setlocale(locale.LC_ALL, self.configParser[self.sectionDefault]["LC_ALL"])
            except locale.Error:
                raise ConfigManagerInvalidException(
                    Errors.ErrorMessenger.CODE_INVALID_CONFIG,
                    "Nevalidní konfigurační soubor. Nepodařilo se nastavit LC_ALL: " +
                    self.configParser[self.sectionDefault]["LC_ALL"])
        return result

    def __transformFilters(self):
        """
        Převede hodnoty pro FILTERS a validuje je.

        :returns: dict -- ve formátu jméno prametru jako klíč a k němu hodnota parametru
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """
        result = {"LANGUAGES": None, "REGEX_NAME": None, "ALLOWED_ALPHABETIC_CHARACTERS": None, "SCRIPT": None}

        if self.configParser[self.sectionFilters]["LANGUAGES"]:
            result["LANGUAGES"] = set(l for l in self.configParser[self.sectionFilters]["LANGUAGES"].split())

        if self.configParser[self.sectionFilters]["REGEX_NAME"]:
            try:
                result["REGEX_NAME"] = re.compile(self.configParser[self.sectionFilters]["REGEX_NAME"])
            except re.error:
                # Nevalidní regex

                raise ConfigManagerInvalidException(
                    Errors.ErrorMessenger.CODE_INVALID_CONFIG,
                    "Nevalidní konfigurační soubor. Nevalidní regulární výraz v "
                    + self.sectionFilters + " u REGEX_NAME.")

        if self.configParser[self.sectionFilters]["ALLOWED_ALPHABETIC_CHARACTERS"]:
            result["ALLOWED_ALPHABETIC_CHARACTERS"] = set(
                c for c in self.configParser[self.sectionFilters]["ALLOWED_ALPHABETIC_CHARACTERS"].split())

        if self.configParser[self.sectionFilters]["SCRIPT"]:
            result["SCRIPT"] = self.configParser[self.sectionFilters]["SCRIPT"]

        return result

    def __transformGenerators(self):
        """
        Převede hodnoty pro generování a validuje je.

        :returns: dict -- ve formátu jméno prametru jako klíč a k němu hodnota parametru
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """

        result = {
            "ABBRE_FORM_OF_PREPOSITIONS":
                self.configParser[self.sectionGenerators]["ABBRE_FORM_OF_PREPOSITIONS"].lower() == "true",
            "ABBRE_FORM_OF_PREPOSITIONS_USE_ON": set(),
            "GENERATE_DERIV_NAMES": self.configParser[self.sectionGenerators]["GENERATE_DERIV_NAMES"].lower() == "true",
            "GENERATE_DERIV_NAMES_TYPES": None if self.configParser[self.sectionGenerators]["GENERATE_DERIV_NAMES_TYPES"] is None else set(self.configParser[self.sectionGenerators]["GENERATE_DERIV_NAMES_TYPES"].split()),
        }

        for nameT in self.configParser[self.sectionGenerators]["ABBRE_FORM_OF_PREPOSITIONS_USE_ON"].split():
            try:
                if nameT == "M":  # obecně muži
                    result["ABBRE_FORM_OF_PREPOSITIONS_USE_ON"].add(Name.Type.PersonGender.MALE)
                elif nameT == "F":  # obecně ženy
                    result["ABBRE_FORM_OF_PREPOSITIONS_USE_ON"].add(Name.Type.PersonGender.FEMALE)
                else:
                    result["ABBRE_FORM_OF_PREPOSITIONS_USE_ON"].add(Name.Type(nameT))
            except ValueError:
                # Nevalidní druh terminálu
                raise ConfigManagerInvalidException(
                    Errors.ErrorMessenger.CODE_INVALID_CONFIG,
                    "Nevalidní konfigurační soubor. ABBRE_FORM_OF_PREPOSITIONS_USE_ON: " + nameT)

        return result

    def __transformGrammar(self):
        """
        Převede hodnoty pro GRAMMAR a validuje je.

        :returns: dict -- ve formátu jméno prametru jako klíč a k němu hodnota parametru
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """

        result = {
            "PARSE_UNKNOWN_ANALYZE": True if self.configParser[self.sectionGrammar][
                                                 "PARSE_UNKNOWN_ANALYZE"].lower() == "true" else False,
            "PARSE_UNKNOWN_ANALYZE_TERMINAL_MATCH": set(),
            "TIMEOUT": None,
        }

        if result["PARSE_UNKNOWN_ANALYZE"]:

            for t in self.configParser[self.sectionGrammar]["PARSE_UNKNOWN_ANALYZE_TERMINAL_MATCH"].split():
                try:
                    result["PARSE_UNKNOWN_ANALYZE_TERMINAL_MATCH"].add(Terminal.Type(t))
                except ValueError:
                    # Nevalidní druh terminálu

                    raise ConfigManagerInvalidException(
                        Errors.ErrorMessenger.CODE_INVALID_CONFIG,
                        "Nevalidní konfigurační soubor. PARSE_UNKNOWN_ANALYZE_TERMINAL_MATCH: " + t)

        try:
            if self.configParser[self.sectionGrammar]["TIMEOUT"].upper() != "NONE":
                result["TIMEOUT"] = int(self.configParser[self.sectionGrammar]["TIMEOUT"])
                if result["TIMEOUT"] <= 0:
                    raise ValueError
        except ValueError:
            # Nevalidní hodnota pro timeout.

            raise ConfigManagerInvalidException(
                Errors.ErrorMessenger.CODE_INVALID_CONFIG,
                "Nevalidní konfigurační soubor. " + self.sectionGrammar + "/TIMEOUT: " +
                self.configParser[self.sectionGrammar]["TIMEOUT"])
        return result

    def __transformDataFiles(self):
        """
        Převede hodnoty pro DATA_FILES a validuje je.

        :returns: dict -- ve formátu jméno prametru jako klíč a k němu hodnota parametru
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """

        result = {
            "GRAMMAR_MALE": self.configParser[self.sectionDataFiles]["GRAMMAR_MALE"],
            "GRAMMAR_FEMALE": self.configParser[self.sectionDataFiles]["GRAMMAR_FEMALE"],
            "GRAMMAR_LOCATIONS": self.configParser[self.sectionDataFiles]["GRAMMAR_LOCATIONS"],
            "GRAMMAR_EVENTS": self.configParser[self.sectionDataFiles]["GRAMMAR_EVENTS"],
            "TITLES": self.configParser[self.sectionDataFiles]["TITLES"],
            "EQ_GEN": self.configParser[self.sectionDataFiles]["EQ_GEN"],
            "MA": self.configParser[self.sectionDataFiles]["MA"],
            "LANGUAGES_DIRECTORY": self.__makePath(self.configParser[self.sectionDataFiles]["LANGUAGES"])
        }

        return result

    def __loadPathArguments(self, parConf, result):
        """
        Načtení argumentů obsahujícíh cesty.

        :param parConf: Sekce konfiguračního souboru v němž hledáme naše hodnoty.
        :type parConf: dict
        :param result: Zde se budou načítat cesty. Názvy klíčů musí odpovídat názvům argumentů.
        :type result: dict
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """

        for k in result.keys():
            if parConf[k]:
                result[k] = self.__makePath(parConf[k])
            else:
                raise ConfigManagerInvalidException(Errors.ErrorMessenger.CODE_INVALID_CONFIG, "Nevalidní "
                                                                                               "konfigurační soubor. "
                                                                                               "Chybí " +
                                                    self.sectionDataFiles + " -> " + k)

    @staticmethod
    def __makePath(pathX):
        """
        Převede cestu na bezpečný tvar.
        Absolutní cesty jsou ponechány, tak jak jsou. K relativním
        je připojena cesta ke skriptu.

        :param pathX: cesta
        :type pathX: str
        """
        if os.path.isabs(pathX):
            return pathX
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), pathX)


class ArgumentParserError(Exception):
    pass


class ExceptionsArgumentParser(ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)


class ArgumentsManager(object):
    """
    Arguments manager pro namegen.
    """

    @classmethod
    def parseArgs(cls):
        """
        Parsování argumentů.

        :param cls: arguments class
        :returns: Parsované argumenty.
        """

        parser = ExceptionsArgumentParser(description="namegen je program pro generování tvarů jmen osob a lokací.")

        parser.add_argument("-o", "--output", help="Výstupní soubor. Pokud není uvedeno vypisuje na stdout.", type=str,
                            required=False)
        parser.add_argument("-ew", "--error-words",
                            help="Cesta k souboru, kde budou uložena slova, která poskytnutý morfologický analyzátor "
                                 "nezná. Výsledek je v lntrf formátu s tím, že provádí odhad značko-pravidel pro "
                                 "ženská a mužská jména.",
                            type=str)
        parser.add_argument("-gn", "--given-names",
                            help="Cesta k souboru, kde budou uložena slova označená jako křestní. Výsledek je v lntrf "
                                 "formátu.",
                            type=str)
        parser.add_argument("-sn", "--surnames",
                            help="Cesta k souboru, kde budou uložena slova označená jako příjmení. Výsledek je v "
                                 "lntrf formátu.",
                            type=str)
        parser.add_argument("-l", "--locations",
                            help="Cesta k souboru, kde budou uložena slova označená jako lokace. Výsledek je v lntrf "
                                 "formátu.",
                            type=str)
        parser.add_argument("-in", "--include-no-morphs",
                            help="Vytiskne i názvy/jména, u kterých se nepodařilo získat tvary, mezi výsledky.",
                            action='store_true')
        parser.add_argument("-w", "--whole", help="Na výstupu se budou vyskytovat pouze tvary jmen ve všech pádech.",
                            action='store_true')
        parser.add_argument("-v", "--verbose", help="Vypisuje i příslušné derivace jmen/názvů.", action='store_true')
        parser.add_argument("-d", "--deriv",
                            help="Roztřídí jména do tříd ekvivalence, na základě relace MÁ STEJNOU DERIVACI, a "
                                 "vytiskne náhodné reprezentanty (jména) derivací do souboru, který udává tento parametr. Budou zde jen ta jména, která se opravdu generovala.",
                            type=str, required=False)
        parser.add_argument("--deriv-stat",
                            help="Vypíše do souboru statistiky jednotlivých derivací. ",
                            type=str, required=False)
        parser.add_argument('input', nargs="?",
                            help='Vstupní soubor se jmény. Pokud není uvedeno očekává vstup na stdin.', default=None)
        parser.add_argument("--def-lang",
                            help="Jazyk, který bude použit jako výchozí v případě neznámého jazyka (výchozí cs).",
                            type=str, required=False, default="cs")

        parsed = None

        try:
            parsed = parser.parse_args()

        except ArgumentParserError as e:
            parser.print_help()
            print("\n" + str(e), file=sys.stderr, flush=True)
            Errors.ErrorMessenger.echoError(
                Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_INVALID_ARGUMENTS),
                Errors.ErrorMessenger.CODE_INVALID_ARGUMENTS)

        return parsed


def priorityDerivationFilter(aTokens: List[List[namegenPack.Grammar.AnalyzedToken]]):
    """
    Filtrování derivací na základě priorit terminálů.

    Příklad:
            1. derivace: Adam F    P:::M    Adam[k1gMnSc1]#G F[k1gNnSc1]#S ...
                Adam    1{p=0, c=1, t=G, g=M, r="^(?!^([sS]vatý|[sS]aint)$).*$", note=jG, n=S}
                F    1{t=S, c=1, p=0, note=jS, g=N, n=S}
            2. derivace (vítězná): Adam F    P:::M    Adam[k1gMnSc1]#G F#I ...
                Adam    1{p=0, c=1, t=G, g=M, r="^(?!^([sS]vatý|[sS]aint)$).*$", note=jG, n=S}
                F    ia{p=1, t=I}

            Díky prioritě p=1 u F ve druhé derivaci bude vybrána pouze tato derivace.

            Samotný výběr probíhá tak, že procházíme pomyslným stromem od kořena( první slovo) a postupně, jak
            procházíme úrovně,
            tak odstraňujeme větve, kde je menší priorita.
            Příklad (pouze priority):
                0 0 0 4
                2 0 0 0

                Bude vybrána druhá derivace, protože jsme první odstřihli již při prvním slově, tudiž vyšší priorita
                není brána v úvahu.

    :param aTokens: Derivace reprezentované pomocí analyzovaných tokenů.
    :type aTokens: List[List[namegenPack.Grammar.AnalyzedToken]]
    :return: Indexy derivací pro odstranění.
    :rtype: List[int]
    """

    if len(aTokens) <= 1:
        # není co filtrovat
        return []

    derivationsLeft = set(x for x in range(len(aTokens)))  # z tohoto setu budeme postupně odebírat

    for iW in range(len(aTokens[0])):
        # pojďme najít maximální prioritu pro aktuální slovo
        maxP = max(
            aTokens[derivIndex][iW].matchingTerminal.getAttribute(Terminal.Attribute.Type.PRIORITY).value
            for derivIndex in derivationsLeft)

        # odfiltrujeme derivace, které nemají na aktuálním slově maximální prioritu
        derivationsLeft = set(derivIndex for derivIndex in derivationsLeft
                              if aTokens[derivIndex][iW].matchingTerminal.getAttribute(
            Terminal.Attribute.Type.PRIORITY).value >= maxP)

        if len(derivationsLeft) <= 1:
            break

    # Odfiltrovat se mají ty, které se nedostaly až na konec.
    return list(set(x for x in range(len(aTokens))) - derivationsLeft)


def equGen(names: List[Name], languages: Dict[str, Language]) -> List[Name]:
    """
    Generuje nová jména s ekvivalentními slovy (ml. mladší).

    :param names: Všechna jména pro rozgenerování.
    :type names: List[Name]
    :param languages: Jazyky, které chceme použít.
    :type languages: Dict[str, Language]
    :return: Rozgenerovaná jména.
    :rtype: List[Name]
    """

    interestingWords = defaultdict(lambda: defaultdict(set))
    for code, lng in languages.items():
        for nameType, eqSets in lng.eqGen.items():
            for eSet in eqSets:
                interestingWords[code][Name.Type(nameType)] = interestingWords[code][Name.Type(nameType)].union(eSet)

    generatedNames = []
    for name in names:
        newWords = []
        shouldGenerate = False

        if name.language is None:
            # unknown language we must skip it
            continue

        for word in name:
            word = str(word)

            try:
                if word in interestingWords[name.language.code][name.type]:
                    shouldGenerate = True
                    allEq = set()
                    for eqSet in name.language.eqGen[str(name.type)]:
                        if word in eqSet:
                            allEq = allEq.union(eqSet)
                    newWords.append(list(allEq))
                else:
                    newWords.append([word])
            except KeyError:
                # pro tento druh slova a jazyk nemáme množinu ekvivalentních slov
                continue

        if shouldGenerate:
            # generate new name
            """
            Toy Example:
                0 [A,B] 1 [a,b,c] 2 [x,y]
                ->
                0 A 1 a 2 x
                0 B 1 a 2 x
                0 A 1 b 2 x
                0 B 1 b 2 x
                0 A 1 c 2 x
                0 B 1 c 2 x
                0 A 1 a 2 y
                0 B 1 a 2 y
                0 A 1 b 2 y
                0 B 1 b 2 y
                0 A 1 c 2 y
                0 B 1 c 2 y
            """

            numberOfVariants = reduce(lambda x, y: x * len(y), newWords, 1)

            for variantOffset in range(numberOfVariants):
                lastPeriod = 1  # number of items in a last words period
                newName = name.copy()
                for wordsOffset, words in enumerate(newWords):
                    newName.words[wordsOffset] = Word(words[(variantOffset // lastPeriod) % len(words)], newName,
                                                      wordsOffset)
                    lastPeriod *= len(words)

                newName.generated = True
                generatedNames.append(newName)

    return generatedNames


def gramAnalyzeName(name: Name, tokens: List[Token]) -> \
        Tuple[List[List[namegenPack.Grammar.Rule]], List[List[namegenPack.Grammar.AnalyzedToken]]]:
    """
    Provedou analýzu na základě správné gramatiky, která má být použita pro dané jméno.

    :param name: Jméno pro analýzu.
    :type name: Name
    :param tokens: Tokeny z lexikální analýzy.
    :type tokens: List[Token]
    :return: Analyze for given name.
    :rtype: Tuple[List[List[namegenPack.Grammar.Rule]], List[List[namegenPack.Grammar.AnalyzedToken]]]
    :raise NotInLanguage: Řetězec není v jazyce generovaným danou gramatikou.
    :raise TimeoutException: Při provádění syntaktické analýzy, nad daným řetězcem, došlo k timeoutu.
    :raise ExceptionMessageCode: je cosi prohnilého ve stavu tohoto programu
    """
    # rules a aTokens může obsahovat více než jednu možnou derivaci

    rules, aTokens = name.grammar.analyse(tokens)

    return rules, aTokens


def writeDerivStat(writeTo: str, derivClasses: Dict[str, Dict[str, Dict[List[Grammar.Rule], Dict[bool, Set[Name]]]]]):
    """
    Vypíše statistiky derivací do souboru.

    :param writeTo: Cesta k souboru kam se má vypisovat.
    :param derivClasses: Jedná se o data pro každý jazyk a jemu příslušnou gramatiku pro danou derivaci.
        V podobě [jazyk][gramatika][derivace][True/False - False jména s neznámou analýzou slova] = množina jmen.
    """

    with open(writeTo, "w") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            ["language", "grammar type", "known words only", "number of names", "representative", "derivative",
             "name line"])
        for lang, types in sorted(derivClasses.items(), key=lambda s: s[0]):
            for typeG, allDerivations in sorted(types.items(), key=lambda s: s[0]):
                for deriv, knownUnknownGroups in sorted(allDerivations.items(),
                                                        key=lambda d: sum(len(x) for x in d[1].values()), reverse=True):
                    # iteruje přes derivace, od derivace s největším počtem jmen po nejmenší počet jmen
                    for unknownFlag in [True, False]:  # True -> všechna slove ve jméne jsou známa
                        names = knownUnknownGroups[unknownFlag]
                        if len(names) > 0:
                            representative = next(iter(names))
                            writer.writerow([lang, typeG, unknownFlag, len(names), representative,
                                             " | ".join(str(d) for d in deriv), repr(representative)])


def writeDerivRep(writeTo: str, derivClasses: Dict[str, Dict[str, Dict[List[Grammar.Rule], Dict[bool, Set[Name]]]]]):
    """
    Vypíše reprezentanty (jména) derivací do souboru.

    :param writeTo: Cesta k souboru kam se má vypisovat.
    :param derivClasses: Jedná se o data pro každý jazyk a jemu příslušnou gramatiku pro danou derivaci.
        V podobě [jazyk][gramatika][derivace][True/False - False jména s neznámou analýzou slova] = množina jmen.
    """

    with open(writeTo, "w") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["language", "grammar type", "known words only",
                         "number of names that shares derivation with representative", "class representative"])
        # number of names - počet jmen, které sdílý derivaci s reprezentantem

        for lang, types in sorted(derivClasses.items(), key=lambda s: s[0]):
            for typeG, allDerivations in sorted(types.items(), key=lambda s: s[0]):

                # následující struktury jsou zde ve dvou verzích False/True, které rozdělují jména bez/s slovy nemající
                # analýzu

                selectedNames = {False: set(), True: set()}
                selectedNamesShared = {False: {},
                                       True: {}}  # každé jméno bude mít zde množinu jmen sdílejících s ním derivaci

                for deriv, knownUnknownGroups in allDerivations.items():
                    for unknownFlag, names in knownUnknownGroups.items():
                        if len(names) > 0:
                            # skupina obsahuje/neobsahuje slova bez analýzy není prázdná

                            sharedNames = names & selectedNames[unknownFlag]
                            if len(sharedNames) == 0:
                                representative = next(iter(names))
                                selectedNames[unknownFlag].add(representative)
                                selectedNamesShared[unknownFlag][representative] = names.copy()

                            else:
                                # tato derivace je již pokryta nějakým jménem z selectedNames
                                for sN in sharedNames:
                                    selectedNamesShared[unknownFlag][sN] |= names

                for unknownFlag in [True, False]:
                    for name, sharedNames in sorted(selectedNamesShared[unknownFlag].items(), key=lambda x: len(x[1]),
                                                    reverse=True):
                        writer.writerow([lang, typeG, unknownFlag, len(sharedNames), repr(name)])


def langLoad(configAll: Dict) -> Dict[str, Language]:
    """
    Načtení jazyků.

    :param configAll: programová konfigurace
    :return: Načtené jazyky
        kód jazyka -> jazyk
    """

    languages = {}
    for langFolder in os.listdir(configAll[ConfigManager.sectionDataFiles]["LANGUAGES_DIRECTORY"]):

        langFolder = os.path.join(configAll[ConfigManager.sectionDataFiles]["LANGUAGES_DIRECTORY"], langFolder)
        if os.path.isdir(langFolder):
            try:
                lng = Language(langFolder=langFolder,
                               gFemale=configAll[ConfigManager.sectionDataFiles]["GRAMMAR_FEMALE"],
                               gMale=configAll[ConfigManager.sectionDataFiles]["GRAMMAR_MALE"],
                               gLocations=configAll[ConfigManager.sectionDataFiles]["GRAMMAR_LOCATIONS"],
                               gEvents=configAll[ConfigManager.sectionDataFiles]["GRAMMAR_EVENTS"],
                               titles=configAll[ConfigManager.sectionDataFiles]["TITLES"],
                               eqGen=configAll[ConfigManager.sectionDataFiles]["EQ_GEN"],
                               ma=configAll[ConfigManager.sectionDataFiles]["MA"],
                               gTimeout=configAll[ConfigManager.sectionGrammar]["TIMEOUT"])

                languages[lng.code] = lng
            except Errors.ExceptionMessageCode as e:
                raise Errors.ExceptionMessageCode(e.code, langFolder + ": " + e.message)

    return languages


def initMorphoAnalyzers(allWords: Set[Word], languages: Dict[str, Language], configAll: Dict):
    """
    Provede inicializaci morfologických analyzátoru pro dané jazyky.

    :param allWords: Všechna slova pro všechny jazyky.
    :param languages: jazyky jejichž morfologické analyzátory chceme inicializovat
    :param configAll: programová konfigurace
    """

    # filtrace slov do příslušných jazyků

    langWords = {lngCode: set() for lngCode in languages}

    for word in allWords:
        try:
            langWords[word.name.language.code].add(str(word))
        except KeyError:
            # naznámý jazyk
            continue

    for code, lang in languages.items():
        lang.initMAnalyzer(langWords[code])


def prepareNameDependantAnalysys(names: NameReader, languages: Dict[str, Language]):
    """
    Provede přípravu na jméně závislé analýzy pro všechny jazyky.

    :param names: všechna uvažovaná jména
    :param languages: Všechny uvažované jazyky, které chceme použít.
    """

    # filtrace jmen do příslušných jazyků

    langNames = {lngCode: [] for lngCode in languages}

    for name in names:
        try:
            langNames[name.language.code].append(name)
        except KeyError:
            # naznámý jazyk
            continue

    for code, lang in languages.items():
        lang.ma.prepareNameDependentAnalysis(langNames[code])


def main():
    """
    Vstupní bod programu.
    """
    try:
        logging.basicConfig(stream=sys.stderr, format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
        # zpracování argumentů
        args = ArgumentsManager.parseArgs()

        # načtení konfigurace
        configManager = ConfigManager()
        configAll = configManager.read(os.path.dirname(os.path.realpath(__file__)) + '/namegen_config.ini')

        if configAll[configManager.sectionGrammar]["PARSE_UNKNOWN_ANALYZE"]:
            # nastavní druhů terminálů UNKNOWN_ANALYZE_TERMINAL_MATCH
            Terminal.UNKNOWN_ANALYZE_TERMINAL_MATCH = configAll[configManager.sectionGrammar][
                "PARSE_UNKNOWN_ANALYZE_TERMINAL_MATCH"]

        # koukneme jestli je tu opravdu validní vychozi jazyk
        if args.def_lang not in set(os.listdir(configAll[configManager.sectionDataFiles]["LANGUAGES_DIRECTORY"])):
            raise ConfigManagerInvalidException(Errors.ErrorMessenger.CODE_INVALID_CONFIG,
                                                f"Nenašel jsem výchozí jazyk {args.def_lang}.")

        # get output
        outF = open(args.output, "w") if args.output else sys.stdout

        derivClassesOutput = args.deriv
        derivClasses = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(set))))
        # derivClasses je dict formátu:
        #   [jazyk][gramatika][derivace][True/False - False jména s neznámou analýzou slova] = množina jmen

        logging.info("načtení jazyků")
        languages = langLoad(configAll)
        logging.info("\thotovo")

        useLanguages = configAll[configManager.sectionFilters]["LANGUAGES"]
        if useLanguages is None:
            # uživatel nezadal žádný filtr, odfiltrujeme tedy jen neznámé jazyky
            useLanguages = set(langCode for langCode in languages)

        namesFilter = NamesFilter(useLanguages,
                                  configAll[configManager.sectionFilters]["REGEX_NAME"],
                                  configAll[configManager.sectionFilters]["ALLOWED_ALPHABETIC_CHARACTERS"],
                                  configAll[configManager.sectionFilters]["SCRIPT"])

        # Inicializace generátorů.
        # Je to dělané jako funktor, aby to bylo do budoucna případně snadněji rozšířitelné. Podobně jako filtry.
        generators = []

        if configAll[configManager.sectionGenerators]["ABBRE_FORM_OF_PREPOSITIONS"]:
            generators.append(
                GenerateAbbreFormOfPrep(configAll[configManager.sectionGenerators]["ABBRE_FORM_OF_PREPOSITIONS_USE_ON"])
            )

        if configAll[configManager.sectionGenerators]["GENERATE_DERIV_NAMES"]:
            generators.append(GenerateDerivatedForms(configAll[configManager.sectionGenerators]["GENERATE_DERIV_NAMES_TYPES"]))

        generateNewNames = MultiGenerator(generators) if len(generators) > 0 else GenerateNope()

        logging.info("čtení jmen")
        # načtení jmen pro zpracování
        namesR = NameReader(languages=languages,
                            langDef=args.def_lang,
                            inputFile=args.input,
                            shouldSort=False)
        logging.info("\thotovo")

        logging.info("Filtrace jmen")
        namesR.filter(namesFilter, outF if args.include_no_morphs else None)
        logging.info("\thotovo")

        logging.info("Rozgenerování ekvivalentních vstupů")

        generatedNames = equGen(namesR.names, languages)
        namesR.names = namesR.names + generatedNames  # must to add it here because of the analyzer

        logging.info("\thotovo")

        logging.info("analýza slov")

        # přiřazení morfologických analyzátoru
        # Tyto analyzátory jsou nastaveny tak, že z ma ignorují všechny hovorové tvary.

        initMorphoAnalyzers(namesR.allWords(True), languages, configAll)

        logging.info("\thotovo")

        namesR.names = namesR.names[:len(namesR.names) - len(generatedNames)]   # nepotrebujeme jiz egenerovana jmen, protoze jsou v analyze, a pridame je znovu po filtrovani

        logging.info("Filtrace rozgenerovaných vstupů")

        filterGrammar = NamesGrammarFilter()

        for name in generatedNames:
            if filterGrammar(name):
                # chceme jen ta jména, která jsou v jazyku generovným přislušnou gramatikou
                namesR.names.append(name)

        logging.info("\thotovo")

        logging.info("analýza slov závislá na jménu")
        prepareNameDependantAnalysys(namesR, languages)

        logging.info("\thotovo")

        logging.info("Řazení jmen")

        namesR.sortNames()

        logging.info("\thotovo")

        logging.info("generování tvarů")

        # čítače chyb
        errorsOthersCnt = 0
        errorsGrammerCnt = 0  # není v gramatice
        errorsUnknownNameType = 0  # není v gramatice
        errorsDuplicity = 0  # více stejných jmen (včetně typu)
        errorsTimout = 0  # U kolika jmen došlo k timeoutu při syntaktické analýze.

        errorWordsShouldSave = True if args.error_words is not None else False

        # slova ke, kterým nemůže vygenerovat tvary, zjistit POS...
        # Klíč čtveřice (druh názvu (mužský, ženský, lokace),druhu slova ve jméně, dané slovo).
        # Hodnota je množina dvojic jméno/název, kde se problém vyskytl a boolean zda dané jméno má více než jednu
        # derivace (True více derivací).
        errorWords = {}

        # slouží pro výpis křestních jmen, příjmení atd.
        wordRules = {}
        writeWordsOfTypeTo = {}
        if args.given_names is not None:
            # uživatel chce vypsat křestní jména do souboru
            wordRules[WordTypeMark.GIVEN_NAME] = {}
            writeWordsOfTypeTo[WordTypeMark.GIVEN_NAME] = args.given_names

        if args.surnames is not None:
            # uživatel chce příjmení jména do souboru
            wordRules[WordTypeMark.SURNAME] = {}
            writeWordsOfTypeTo[WordTypeMark.SURNAME] = args.surnames

        if args.locations is not None:
            # uživatel chce vypsat slova odpovídají lokacím do souboru
            wordRules[WordTypeMark.LOCATION] = {}
            writeWordsOfTypeTo[WordTypeMark.LOCATION] = args.locations

        cnt = 0  # projito jmen

        # nastaveni logování
        duplicityCheck = set()  # zde se budou ukládat jména pro zamezení duplicit

        startOfGenMorp = time.time()

        for name in namesR:

            if name.language is None:
                # neidentifikovaný jazyk
                print(Errors.ErrorMessenger.getMessage(
                    Errors.ErrorMessenger.CODE_UNKNOWN_LANGUAGE).format(str(name)), file=sys.stderr, flush=True)

                if args.include_no_morphs:
                    # uživatel chce vytisknout i slova bez tvarů
                    print(name.printName(), file=outF)

                continue

            lang = languages[name.language.code]

            morphsPrinted = False

            wNoInfo = set()  # Zde budou uložena slova nemající analýzu, která by ji měla mít.

            try:
                if name in duplicityCheck:
                    # již jsme jednou generovali
                    errorsDuplicity += 1
                    continue

                duplicityCheck.add(name)

                tokens = lang.lex.getTokens(name)

                wordsMarks = []
                for tokenPos, t in enumerate(tokens):
                    if t.type == Token.Type.ANALYZE_UNKNOWN:
                        # Vybíráme ty tokeny, pro které není dostupná analýza a měla by být.

                        # Musíme přidat druh jména získaný pomocí simpleWordsTypesGuess, protože nemůžeme použít
                        # bud použít syntaktickou analýzu (PARSE_UNKNOWN_ANALYZE=FALSE)
                        # a i kdybychom ji použít mohli, tak v případě, kdy nebude název v jazyce generovaným danou
                        # gramtikou, tak nedostaneme požadovaná značení.
                        try:
                            wNoInfo.add((t.word, wordsMarks[tokenPos]))
                        except IndexError:
                            # Nemáme analýzu druhu slov pomocí simpleWordsTypesGuess
                            wordsMarks = name.simpleWordsTypesGuess(tokens)
                            wNoInfo.add((t.word, wordsMarks[tokenPos]))

                if (configAll[configManager.sectionGrammar]["PARSE_UNKNOWN_ANALYZE"] or len(wNoInfo) == 0) \
                        and len(wNoInfo) != len(name.words):
                    # Nechceme vůbec používat grammatiku na názvy/jména, které obsahují slova, které morfologický
                    # analyzátor nezná nebo jméno/název je složen pouze z takovýchto slov.

                    # zpochybnění odhad typu jména
                    # protože guess type používá také gramatky
                    # tak si případný výsledek uložím, abychom nemuseli dělat 2x stejnou práci
                    tmpRes = name.guessType(tokens)
                    if tmpRes is not None:
                        rules, aTokens = tmpRes
                    else:
                        rules, aTokens = None, None

                    if name.type == None:  # Používáme rozšířené porovnání implementované v Name.__eq__.
                        # Nemáme dostatečnou informaci o druhu jména, jdeme dál.
                        print(Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_NAME_WITHOUT_TYPE).format(
                            str(name)), file=sys.stderr, flush=True)
                        errorsUnknownNameType += 1
                        if args.include_no_morphs:
                            # uživatel chce vytisknout i slova bez tvarů
                            print(name.printName(), file=outF)
                        continue
                    # Vybrání a zpracování gramatiky na základě druhu jména.
                    # získáme aplikovatelná pravidla, ale hlavně analyzované tokeny, které mají v sobě informaci,
                    # zda-li se má dané slovo ohýbat, či nikoliv a další

                    if aTokens is None:  # Nedostaly jsme aTokeny při určování druhu slova?
                        # rules a aTokens může obsahovat více než jednu možnou derivaci
                        rules, aTokens = gramAnalyzeName(name, tokens)

                    completedMorphs = set()  # pro odstranění dualit používáme set
                    noMorphsWords = set()
                    missingCaseWords = set()

                    if configAll[configManager.sectionDefault]["ALLOW_PRIORITY_FILTRATION"]:
                        # filtr derivací na základě priorit terminálů
                        for r in sorted(priorityDerivationFilter(aTokens),
                                        reverse=True):  # musíme jít od konce, protože se při odstranění mění indexy
                            # odstranění derivací na základě priorit
                            del rules[r]
                            del aTokens[r]

                    alreadyGenerated = set()  # mnozina ntic analyzovanych terminalu, ktere byly jiz generovany

                    generatedNamesThatShouldBeInDuplicityCheckSet = set()
                    for ru, aT in zip(rules, aTokens):
                        if derivClassesOutput is not None:
                            # ulož jméno do příslušné třídy na základě derivace
                            derivClasses[name.language.code][os.path.basename(name.grammar.filePath)][tuple(ru)][
                                all(tmpAT.token.type != Token.Type.ANALYZE_UNKNOWN for tmpAT in aT)].add(name)
                        aTTuple = tuple(aT)
                        if aTTuple in alreadyGenerated:
                            # Nechceme zpracovávat co jsme již zpracovávali.
                            # K jedné větě může existovat vícero derivací, proto je nutná tato kontrola.
                            continue

                        alreadyGenerated.add(aTTuple)
                        try:

                            if configAll[configManager.sectionGrammar]["PARSE_UNKNOWN_ANALYZE"]:

                                for t in aT:
                                    if t.token.type == Token.Type.ANALYZE_UNKNOWN:
                                        # zaznamenáme slova bez analýzy

                                        # přidáme informaci o druhu slova ve jméně a druh jména
                                        # používá se pro výpis chybových slov

                                        try:
                                            errorWords[(name.orig_language_code, name.language.code, name.type,
                                                        t.matchingTerminal.getAttribute(
                                                            namegenPack.Grammar.Terminal.Attribute.Type.WORD_TYPE).value,
                                                        t.token.word)].add((name, len(rules) > 1))
                                        except KeyError:
                                            errorWords[(name.orig_language_code, name.language.code, name.type,
                                                        t.matchingTerminal.getAttribute(
                                                            namegenPack.Grammar.Terminal.Attribute.Type.WORD_TYPE).value,
                                                        t.token.word)] = {(name, len(rules) > 1)}

                            # Získáme tvary a pokud budou pro nějaké slovo problémy, při získání tvarů, tak si necháme
                            # uložit korespondující token ke slovo do množiny missingCaseWords (společně s problémovým
                            # pádem).
                            morphs = name.genMorphs(aT, missingCaseWords)

                            if args.whole and (
                                    (name.grammar.flexible and len(morphs) < len(Case)) or (
                                    not name.grammar.flexible and len(morphs) < 1)):
                                # Uživatel chce tisknout pouze pokud máme tvary pro všechny pády.
                                continue

                            # Aplikujeme generování nových jmen z existujících.

                            generatedNames = generateNewNames(morphs)
                            generatedNamesNotDuplicit = []

                            for genName, genNameMorphs in generatedNames:
                                if genName not in duplicityCheck:
                                    generatedNamesNotDuplicit.append((genName, genNameMorphs))

                                    # Přidáme nově vygenerovaná jména, abychom je znovu nemuseli případně dále procházet.
                                    generatedNamesThatShouldBeInDuplicityCheckSet.add(genName)

                            generatedNames = generatedNamesNotDuplicit

                            # vypíšeme všechna jména (generovaná + původní jméno)
                            for nameToWrite, morphsToWrite in [(name, morphs)] + generatedNames:
                                if args.whole and (
                                        (name.grammar.flexible and len(morphs) < len(Case)) or (
                                        not name.grammar.flexible and len(morphs) < 1)):
                                    # Uživatel chce tisknout pouze pokud máme tvary pro všechny pády.
                                    # je to tu znovu kvuli nove vygenerovanym
                                    continue
                                resAdd = str(nameToWrite) + "\t" + str(nameToWrite.language.code) + "\t" + str(
                                    nameToWrite.type) + "\t" + (
                                             "|".join(str(m) for m in morphsToWrite))
                                if len(nameToWrite.additionalInfo) > 0:
                                    resAdd += "\t" + ("\t".join(nameToWrite.additionalInfo))
                                if nameToWrite.generated:
                                    resAdd += "\tG"
                                completedMorphs.add(resAdd)
                                if args.verbose:
                                    logging.info(str(nameToWrite) + "\tDerivace:")
                                    for r in ru:
                                        logging.info("\t\t" + str(r))
                                    logging.info("\tTerminály:")
                                    for a in aT:
                                        if a.token.word is not None:
                                            logging.info("\t\t" + str(a.token.word) + "\t" + str(a.matchingTerminal))

                        except Word.WordNoMorphsException as e:
                            # chyba při generování tvarů slova
                            # odchytáváme již zde, jeikož pro jedno slovo může být více alternativ
                            for x in aT:
                                # hledáme AnalyzedToken pro naše problémové slovo, abychom mohli ke slovu
                                # přidat i odhadnutý druh slova ve jméně (křestní, příjmení, ...)
                                if x.token.word == e.word:
                                    noMorphsWords.add((x.matchingTerminal, e.word))
                                    break

                    if len(noMorphsWords) > 0 or len(missingCaseWords) > 0:
                        # chyba při generování tvarů jména

                        if len(noMorphsWords) > 0:
                            print(Errors.ErrorMessenger.getMessage(
                                Errors.ErrorMessenger.CODE_NAME_NO_MORPHS_GENERATED).format(str(name), ", ".join(
                                str(w) + " " + str(m) for m, w in noMorphsWords)), file=sys.stderr, flush=True)

                        for aTerm, c in missingCaseWords:
                            print(str(name) + "\t" + Errors.ErrorMessenger.getMessage(
                                Errors.ErrorMessenger.CODE_WORD_MISSING_MORF_FOR_CASE) + "\t" + str(
                                c.value) + "\t" + str(
                                aTerm.token.word) + "\t" + str(aTerm.matchingTerminal), file=sys.stderr, flush=True)

                    # vytiskneme
                    for m in completedMorphs:
                        print(m, file=outF)

                    if len(completedMorphs) > 0:
                        morphsPrinted = True

                    # Přidáme nově vygenerovaná jména, abychom je znovu nemuseli případně dále procházet.
                    for gn in generatedNamesThatShouldBeInDuplicityCheckSet:
                        duplicityCheck.add(gn)

                    # zjistíme, zda-li uživatel nechce vypsat nějaké typy jmen do souborů

                    for wordType in wordRules:
                        # chceme získat včechny slova daného druhu a k nim příslušná pravidla

                        # sjednotíme všechny derivace
                        for aT in aTokens:
                            # pouze známá
                            aTokensKnown = [aTok for aTok in aT if aTok.token.type != Token.Type.ANALYZE_UNKNOWN]

                            for w, rules in Name.getWordsOfType(wordType, aTokensKnown):
                                try:
                                    wordRules[wordType][str(w)] = wordRules[wordType][str(w)] | rules
                                except KeyError:
                                    wordRules[wordType][str(w)] = rules
                else:
                    for word, word_mark in wNoInfo:
                        try:
                            errorWords[(name.orig_language_code, name.language.code, name.type, word_mark, word)]\
                                .add((name, False))
                        except KeyError:
                            errorWords[(name.orig_language_code, name.language.code, name.type, word_mark, word)]\
                                = {(name, False)}

            except namegenPack.Grammar.Grammar.TimeoutException as e:
                # Při provádění syntaktické analýzy, nad aktuálním jménem, došlo k timeoutu.
                errorsTimout += 1
                print(e.message + "\t" + str(name) + "\t" + str(name.type), file=sys.stderr, flush=True)

            except Word.WordException as e:
                if isinstance(e, Word.WordCouldntGetInfoException):
                    traceback.print_exc()
                    print(str(name) + "asd\t" + e.message, file=sys.stderr, flush=True)

            except namegenPack.Grammar.Grammar.NotInLanguage:
                errorsGrammerCnt += 1
                print(Errors.ErrorMessenger.getMessage(
                    Errors.ErrorMessenger.CODE_NAME_IS_NOT_IN_LANGUAGE_GENERATED_WITH_GRAMMAR) +
                      "\t" + str(name) + "\t" + str(name.type), file=sys.stderr, flush=True)

            except Errors.ExceptionMessageCode as e:
                # chyba při zpracování slova
                errorsOthersCnt += 1
                print(str(name) + "\t" + e.message, file=sys.stderr, flush=True)

            if len(wNoInfo) > 0:
                print(str(name) + "\t" + Errors.ErrorMessenger.getMessage(
                    Errors.ErrorMessenger.CODE_WORD_ANALYZE) + "\t" + (
                          ", ".join(str(w) for w, _ in wNoInfo)),
                      file=sys.stderr, flush=True)

            if args.include_no_morphs and not morphsPrinted:
                # uživatel chce vytisknout i slova bez tvarů
                print(name.printName(), file=outF)
            cnt += 1
            if cnt % 100 == 0:
                logging.info("Projito jmen/názvů: " + str(cnt))

        endOfGenMorp = time.time()

        if args.output:
            # close the output file
            outF.close()

        logging.info("\thotovo")
        # vypíšeme druhy slov, pokud to uživatel chce

        for wordType, pathToWrite in writeWordsOfTypeTo.items():
            logging.info("\tVýpis slov typu: " + str(wordType))
            with open(pathToWrite, "w") as fileW:
                for w, rules in wordRules[wordType].items():
                    print(
                        str(w) + "\t" + "j" + str(wordType) + "\t" + (" ".join(sorted(r.lntrf + "::" for r in rules))),
                        file=fileW)
            logging.info("\thotovo")

        if args.deriv_stat is not None:
            logging.info("Výpis statistik derivací.")
            writeDerivStat(args.deriv_stat, derivClasses)
            logging.info("\thotovo")

        if derivClassesOutput is not None:
            # Uživatel chtěl roztřídit jména do tříd ekvivalence, na základě relace MÁ STEJNOU DERIVACI,
            # a "vytisknout je do souboru. Budou zde jen ta jména, která se opravdu generovala.
            logging.info("Výpis reprezentantů derivací pro všechny gramatiky.")
            writeDerivRep(derivClassesOutput, derivClasses)
            logging.info("\thotovo")

        print("-------------------------", file=sys.stderr)
        print("Celkem jmen: " + str(namesR.errorCnt + len(namesR.names)), file=sys.stderr)
        print("\tNenačtených jmen: " + str(namesR.errorCnt), file=sys.stderr)
        print("\tDuplicitních jmen: " + str(errorsDuplicity), file=sys.stderr)
        print("\tNačtených jmen/názvů celkem: ", len(namesR.names), file=sys.stderr)
        print("\tPrůměrný čas strávený nad generováním tvarů jednoho jména/názvu: ",
              round((endOfGenMorp - startOfGenMorp) / len(namesR.names), 3) if len(namesR.names) > 0 else 0,
              file=sys.stderr)

        for lngCode, lng in languages.items():
            grammarFemale = lng.gFemale
            grammarMale = lng.gMale
            grammarLocations = lng.gLocations
            grammarEvents = lng.gEvents

            print(f"\tJazyk {lngCode}", file=sys.stderr)
            print("\t\tPrůměrný čas strávený nad jednou syntaktickou analýzou napříč gramatikami:",
                  (
                          grammarFemale.grammarEllapsedTime + grammarLocations.grammarEllapsedTime + grammarEvents.grammarEllapsedTime + grammarMale.grammarEllapsedTime) / (
                          grammarFemale.grammarNumOfAnalyzes + grammarMale.grammarNumOfAnalyzes + grammarLocations.grammarNumOfAnalyzes + grammarEvents.grammarNumOfAnalyzes)
                  if (
                             grammarFemale.grammarNumOfAnalyzes + grammarMale.grammarNumOfAnalyzes + grammarLocations.grammarNumOfAnalyzes + grammarEvents.grammarNumOfAnalyzes) > 0 else 0,
                  file=sys.stderr)
            print("\t\t\t FEMALE", file=sys.stderr)
            print("\t\t\t\t Průměrný čas strávený nad jednou syntaktickou analýzou:",
                  grammarFemale.grammarEllapsedTime / grammarFemale.grammarNumOfAnalyzes if grammarFemale.grammarNumOfAnalyzes > 0 else 0,
                  file=sys.stderr)
            print("\t\t\t\t Počet analýz:", grammarFemale.grammarNumOfAnalyzes, file=sys.stderr)
            print("\t\t\t MALE", file=sys.stderr)
            print("\t\t\t\t Průměrný čas strávený nad jednou syntaktickou analýzou:",
                  grammarMale.grammarEllapsedTime / grammarMale.grammarNumOfAnalyzes if grammarMale.grammarNumOfAnalyzes > 0 else 0,
                  file=sys.stderr)
            print("\t\t\t\t Počet analýz:", grammarMale.grammarNumOfAnalyzes, file=sys.stderr)
            print("\t\t\t LOCATION", file=sys.stderr)
            print("\t\t\t\t Průměrný čas strávený nad jednou syntaktickou analýzou:",
                  grammarLocations.grammarEllapsedTime / grammarLocations.grammarNumOfAnalyzes if grammarLocations.grammarNumOfAnalyzes > 0 else 0,
                  file=sys.stderr)
            print("\t\t\t\t Počet analýz:", grammarLocations.grammarNumOfAnalyzes, file=sys.stderr)
            print("\t\t\t EVENTS", file=sys.stderr)
            print("\t\t\t\t Průměrný čas strávený nad jednou syntaktickou analýzou:",
                  grammarEvents.grammarEllapsedTime / grammarEvents.grammarNumOfAnalyzes if grammarEvents.grammarNumOfAnalyzes > 0 else 0,
                  file=sys.stderr)
            print("\t\t\t\t Počet analýz:", grammarEvents.grammarNumOfAnalyzes, file=sys.stderr)
            print("\t\tNeznámý druh jména:", errorsUnknownNameType, file=sys.stderr)
            print("\t\tNepokryto gramatikou:", errorsGrammerCnt, file=sys.stderr)
            print("\t\tPočet jmen, u kterých došlo k timeoutu při syntaktické analýze:", errorsTimout, file=sys.stderr)
            print("\t\tPočet slov, které poskytnutý morfologický analyzátor nezná:",
                  len(set(w for (_, _, _, _, w), _ in errorWords.items())), file=sys.stderr)

            if errorWordsShouldSave:
                # save words with errors into a file
                with open(args.error_words, "w") as errWFile:
                    for (orig_lang_code, lang, nT, m,
                         w), names in errorWords.items():  # kód jazyka na vstupu, kód jazyka pro zpracování, druh názvu (mužský, ženský, lokace),označení typu slova ve
                        # jméně(jméno, příjmení), společně se jménem
                        # u ženských a mužských jmen přidáme odhad lntrf značky
                        resultStr = f"{orig_lang_code}\t{lang}\t{w}\t{m}"
                        if m in {WordTypeMark.GIVEN_NAME, WordTypeMark.SURNAME}:
                            if nT == Name.Type.PersonGender.FEMALE:
                                resultStr += "\tk1gFnSc1::"
                            if nT == Name.Type.PersonGender.MALE:
                                resultStr += "\tk1gMnSc1::"
                        # přidáme jména/názvy kde se problém vyskytl
                        resultStr += "\t" + str(nT) + "\t@\t" + "\t".join(
                            str(name) + ("\t" + name.additionalInfo[0] if len(name.additionalInfo) > 0 else "")
                            for name, _ in names)  # name.additionalInfo by mělo na první pozici obsahovat URL zdroje
                        resultStr += f"\t{'all names have multiple derivations' if all(multi_deriv for _, multi_deriv in names) else ''} "
                        print(resultStr, file=errWFile)

    except Errors.ExceptionMessageCode as e:
        Errors.ErrorMessenger.echoError(e.message, e.code)
        traceback.print_tb(e.__traceback__)
    except IOError as e:
        Errors.ErrorMessenger.echoError(
            Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_COULDNT_WORK_WITH_FILE) + "\n" + str(e),
            Errors.ErrorMessenger.CODE_COULDNT_WORK_WITH_FILE)
        traceback.print_tb(e.__traceback__)

    except Exception as e:
        print("--------------------", file=sys.stderr)
        print("Detail chyby:\n", file=sys.stderr)
        traceback.print_tb(e.__traceback__)

        print("--------------------", file=sys.stderr)
        print("Text: ", end='', file=sys.stderr)
        print(e, file=sys.stderr)
        print("--------------------", file=sys.stderr)
        Errors.ErrorMessenger.echoError(Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_UNKNOWN_ERROR),
                                        Errors.ErrorMessenger.CODE_UNKNOWN_ERROR)


if __name__ == "__main__":
    main()
