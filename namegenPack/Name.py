"""
Created on 17. 6. 2018
Modul se třídami pro reprezentaci jména/názvu.

:author:     Martin Dočekal
:contact:    xdocek09@stud.fit.vubtr.cz
"""

import locale
import logging
import sys
from builtins import str
from enum import Enum
from typing import List, Dict, Set, Tuple, Union, Optional, TextIO

import namegenPack.Grammar
from namegenPack import Errors
from namegenPack.Filters import Filter
from namegenPack.Grammar import Terminal, Token
from namegenPack.Language import Language
from namegenPack.Word import Word, WordTypeMark
from namegenPack.morpho import MorphCategories
from namegenPack.morpho.MorphCategories import Case, POS, Note
from namegenPack.morpho.MorphoAnalyzer import MARule


class NameMorph(object):
    """
    Tvar jména pro nějaký pád.
    Lze použít pro výpis pádu daného jména.
    """

    UNKNOWN_ANALYZE_FLAG = "E"

    def __init__(self, forName, wordsMorphs: List[Set[Tuple[str, Union[MARule, None]]]],
                 wordsTypes: List[Tuple[WordTypeMark, bool]]):
        """
        Vytvoření tvaru jména pro dané jméno.

        :param forName: Vytvořený tvar patří k tomuto jménu.
        :type forName:vName
        :param wordsMorphs: Vygenerované tvary slov společně s jejich značko pravidly.
        Slovo může mít i více tvarů pro konkrétní pád, proto máme list množin.
        Pravidla, obsahující značky, budou uvedeny posplu s vygenervanými tvary slov.
        :type wordsMorphs: List[Set[Tuple[str, Union[MARule, None]]]]
        :param wordsTypes: List dvojic s druhy slov ve jméně společně s informací zdali se má
            uvést příznak informující i chybějící analýze.
            Uvádí se u daného tvaru.
            Počet musí být stejný jako počet slov (počet položek v listu morphs).
            Dvojice: (word type, příznak (E)) U příznaku True znamená přidání UNKNOWN_ANALYZE_FLAG. False
            nepřidává nic.
        :type wordsTypes: List[Tuple[WordTypeMark, bool]]
        """

        self.forName = forName
        self.wordsMorphs = wordsMorphs
        self.wordsTypes = wordsTypes

    def __str__(self):
        morph = ""

        for i, (wordMorphs, wordType) in enumerate(zip(self.wordsMorphs, self.wordsTypes)):
            actMorphsTags = ""

            #druh slova jméno, příjmení...
            if wordType[0] != WordTypeMark.UNKNOWN:
                actMorphsTags = "#" + str(wordType[0].value) + (self.UNKNOWN_ANALYZE_FLAG if wordType[1] else "")

            #slovo / možné varianty slova s lntrf značko pravidly a druhem slova
            morph += "/".join(wordMorph +
                              ("[" + morphRule.lntrfWithoutNote + "]" if morphRule is not None else "") +
                              actMorphsTags
                              for wordMorph, morphRule in wordMorphs)

            # přidání oddělovače slov
            if i < len(self.forName.separators):
                putSep = self.forName.separators[i]
                # přidáváme mezeru nulové délky, pokud neni separator
                morph += putSep if len(putSep) > 0 else u'\u200b'

        return morph


class Name(object):
    """
    Reprezentace celého jména osoby či lokace.
    """

    class NameCouldntCreateException(Errors.ExceptionMessageCode):
        """
        Nepodařilo se vytvořit jméno. Deatil ve zprávě
        """
        pass

    class Type(object):
        """
        Přípustné druhy jmen.
        
        Podporuje rozšířené porovnání pomocí ==.
        Mimo klasické rovnosti je možné se ptát i například následujícím způsobem.
        
        Příklad dotazu na MainType:
            Je x lokace?
                x == MainType.LOCATION
        
        Příklad dotazu na pohlaví:
            Je x jméno ženy?
                x== PersonGender.FEMALE
        
        Zjištění zda je druh x plně určen pro výběr vhodné gramatiky (true není):
            x == None
        """

        INDEX_OF_MAIN_TYPE = 0
        INDEX_OF_FUTURE_PURPOSES = 2
        INDEX_OF_PERSONS_GENDER = 3

        class MainType(Enum):
            """
            Hlavní druh jména.
            """
            LOCATION = "L"
            EVENTS = "E"
            PERSON = "P"

            def __str__(self):
                return self.value

        class PersonGender(Enum):
            """
            Pohlaví osoby.
            """
            MALE = "M"
            FEMALE = "F"

            def __str__(self):
                return self.value

        def __init__(self, nType):
            """
            Vytvoří druh jména.
            
            :param nType: Druh jména.
                #Formát řetězce pro jména osob:
                #    <Type: P=Person>:<Subtype: F/G=Fictional/Group>:<Future purposes: determine regular name and alias>:<Gender: F/M=Female/Male>
                #    Pokud se bude měnit formát je nutná úprava v metodě Name.guessType.
                #Pro názvy lokací je to jen značka L.
            :type nType: str
            :raise ValueError: Při nevalidnim vstupu.
            """

            self.levels = [x if len(x) > 0 else None for x in nType.split(":")]

            # validace hodnot
            # prozatím validujeme pouze MainType a PersonGender, protože se toho více nepoužívá.
            # Ostatní pouze uchováváme pro pozdější výpis a možnost porovnání jmen.

            self.levels[self.INDEX_OF_MAIN_TYPE] = self.MainType(self.levels[self.INDEX_OF_MAIN_TYPE])
            if self.levels[self.INDEX_OF_MAIN_TYPE] == self.MainType.PERSON:
                # Jedná se o osobu, tak validujeme pohlaví.
                if self.levels[self.INDEX_OF_PERSONS_GENDER] is not None:
                    self.levels[self.INDEX_OF_PERSONS_GENDER] = self.PersonGender(
                        self.levels[self.INDEX_OF_PERSONS_GENDER])

        def __hash__(self):
            """
            Vlastnost, že dva objekty pro které vrací __eq__ true mají stejný hash je splněna pouze
            pro porovnání objektů této třídy a nemusí tedy platit pro rozšířené vyhledávání (viz __eq__).
            """
            return hash(str(self))

        def __eq__(self, other):
            """
            Implementuje i rozšířené porovnání:
            Příklad dotazu na MainType:
                Je x lokace?
                    x == MainType.LOCATION
            
            Příklad dotazu na pohlaví:
                Je x jméno ženy?
                    x== PersonGender.FEMALE
            
            Zjištění zda je druh x plně určen pro výběr vhodné gramatiky (true není):
                x == None
                
            """
            if other is None:
                # Zjištění zda je druh x plně určen pro výběr vhodné gramatiky
                if self.levels[self.INDEX_OF_MAIN_TYPE] == self.MainType.PERSON and \
                        self.levels[self.INDEX_OF_PERSONS_GENDER] == other:
                    # není
                    return True

            if isinstance(other, self.__class__):
                # druhý je také typ
                # klasicky porovnáme
                return str(self) == str(other)

            if isinstance(other, self.MainType):
                # porovnání na úrorvni main type
                if self.levels[self.INDEX_OF_MAIN_TYPE] == other:
                    return True

            if isinstance(other, self.PersonGender):
                # porovnání na úrovni osob
                if self.levels[self.INDEX_OF_MAIN_TYPE] == self.MainType.PERSON and \
                        self.levels[self.INDEX_OF_PERSONS_GENDER] == other:
                    return True

            return False

        def __str__(self):
            return ":".join("" if x is None else str(x) for x in self.levels)

    def __init__(self, name, orig_language_code: str, language: Language, nType, addit=None):
        """
        Konstruktor jména.

        :param name: Řetězec se jménem.
        :type name: String
        :param orig_language_code: Originální kód jazyk uvedený u jména.
        :type orig_language_code: str
        :param language: Jazyk tohoto jména, který má být použit pro zpracování.
        :type language: Language
        :param nType: Druh jména.
        :type nType: str
        :param addit: Přídavné info ke jménu
        :type addit: List
        :raise NameCouldntCreateException: Nelze vytvořit jméno.
        """

        if addit is None:
            addit = []

        self._orig_language_code = orig_language_code
        self._language = language
        self._type = None if len(nType) == 0 else nType
        self.additionalInfo = addit
        self.generated = False
        try:
            # nejprve převedeme a validujeme druh jména

            # Pokud None a předpokládáme název pro osobu,tak později může být určeno její pohlaví
            # pomocí guessType.
            if self._type is not None:
                self._type = self.Type(nType)
        except ValueError:
            raise self.NameCouldntCreateException(Errors.ErrorMessenger.CODE_INVALID_INPUT_FILE_UNKNOWN_NAME_TYPE,
                                                  Errors.ErrorMessenger.getMessage(
                                                      Errors.ErrorMessenger.CODE_INVALID_INPUT_FILE_UNKNOWN_NAME_TYPE) + "\n\t" + name + "\t" + nType)

        # rozdělíme jméno na jednotlivá slova a oddělovače
        words, self._separators = self._findWords(name)
        self._words = [Word(w, self, offset) for offset, w in enumerate(words)]

    def copy(self) -> "Name":
        """
        Makes copy of this Name.
        :return: Copy of this name
        :rtype: Name
        """

        return Name(str(self), self._orig_language_code, self._language, None if self._type is None else str(self._type),
                    self.additionalInfo.copy())

    def __str__(self):
        n = ""
        i = 0
        for w in self._words:
            n += str(w)
            if i < len(self._separators):
                n += self._separators[i]
            i += 1

        return n

    def __repr__(self):
        resAdd = str(self) + "\t" + str(self.language.code) + "\t" + str(self.type) + "\t"
        if len(self.additionalInfo) > 0:
            resAdd += "\t".join(self.additionalInfo)

        return resAdd

    def __lt__(self, other):
        # porovnání s ohledem na aktuální locale
        return locale.strxfrm(str(self)) < locale.strxfrm(str(other))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return str(self) == str(other) and self._language == other._language and self._type == other._type

        return False

    def __hash__(self):
        return hash(str(self)) ^ hash(self._language) ^ hash(self._type)

    def __len__(self):
        return len(self._words)

    def __iter__(self):
        for w in self._words:
            yield w

    def __getitem__(self, key):
        return self._words[key]

    def index(self, word: Word, all=False):
        """
        Najde pozici, na které se slovo ve jméně nachází.
        Hledá první shodu (od 0), pokud je all=False.

        :param word: Slovo jehož pozici hledáme.
        :type word: Word
        :param all: Pokud je true, pak hledá všechny výskyty.
        :type all: bool
        :return: Index slova ve jméně. Nebo list indexů všech výskytů.
        :rtype: Union[int, List[int]]
        :raise ValueError: Když není slovo přítomno.
        """

        indexesSoFar=[]
        for i, w in enumerate(self):
            if w == word:
                if all:
                    indexesSoFar.append(i)
                else:
                    return i
        if len(indexesSoFar)>0:
            return indexesSoFar
        else:
            raise ValueError("Word {} is not in name {}.".format(word, self))

    def printName(self, number_of_columns: int = 6):
        """
        Převede jméno do string. Pokud má jméno nějaké přídavné informace, tak je také přidá.
        Formát: <jméno>\TAB<jazyk>\TAB<typeflag>\TAB\TAB<url>
        """

        res = str(self)

        res += "\t" + ("Unknown" if self._language is None else self._language.code)

        res += "\t" + str(self._type)

        res += "\t\t"

        if len(self.additionalInfo) > 0:
            res += ("\t".join(self.additionalInfo))

        missing = number_of_columns - 4 - len(self.additionalInfo)

        if missing > 0:
            res += "\t" * missing

        return res

    def guessType(self, tokens: List[namegenPack.Grammar.Token] = None):
        """
        Provede odhad typu jména. Jedná se o jisté zpochybnění zda-li se jedná o mužské, či ženské jméno.
        Jména lokací a událostí nezpochybňujě.
        Přepíše typ jména pokud si myslí, že je jiný.
        Pokud není typ jména uveden odhadne jej, ovšem pevně předpokládá, že se jedná o jméno osoby.
        (Dle zadání má být automaticky předpokládána osoba, kde se může stát, že typ není uveden.)

        :param tokens: Tokeny odpovídající tomuto jménu. Tento volitelný parametr je zde zaveden pro zrychlení výpočtu, aby nebylo nutné v některých případech
            provádět vícekrát lexikální analýzu. Pokud bude vynechán nic se neděje jen si provede lexikální analýzu sám.
        :type tokens: List[Token]
        :return: Zde vrací analyzované tokeny ( a pravidla), získané při analýze pomocí gramatiky, která generuje jazyk
            v němž je toto jméno. Pokud je jméno ve více gramatikách nebo v žádné vrátí None.
        :rtype aTokens: (List, List) | None
        :raise Word.WordCouldntGetInfoException:Pokud se nepodařilo analyzovat nějaké slovo.
        :raise TimeoutException: Při provádění syntaktické analýzy (pro jednou z gramatik), nad tímto jménem, došlo k timeoutu.
        """
        if self._type != self.Type.MainType.PERSON:
            # zbochybňujeme jen jména a osob
            return
        if not tokens:
            tokens = self.language.lex.getTokens(self)

        # zkusíme zpochybnit typ jména
        changeTo = None
        # najdeme první podstatné nebo přídavné jméno od konce (příjmení)
        # Příjmení jak se zdá může být i přídavné jméno (`Internetová jazyková příručka <http://prirucka.ujc.cas.cz/?id=320#nadpis3>`_.)

        grammars = {Name.Type.PersonGender.FEMALE: self.language.gFemale,
                    Name.Type.PersonGender.MALE: self.language.gMale}
        try:
            if self._language.code == "cs":
                # pro češtinu máme i další kontroly
                for token in reversed(tokens):
                    if token.type == namegenPack.Grammar.Token.Type.ANALYZE:
                        # získáme možné mluvnické kategorie
                        analyze = token.word.info
                        posCat = analyze.getAllForCategory(MorphCategories.MorphCategories.POS,
                                                           {Case.NOMINATIVE})  # máme zájem jen o 1. pád
                        if MorphCategories.POS.NOUN in posCat or MorphCategories.POS.ADJECTIVE in posCat:
                            if token.word[-3:] in {"ová", "cká", "ská"}:
                                # muž s přijmení končícím na ová,cká a ská zřejmě není
                                # změníme typ pokud není ženský
                                changeTo = self.Type.PersonGender.FEMALE
                            break
                    elif token.type == namegenPack.Grammar.Token.Type.ANALYZE_UNKNOWN:
                        # Máme token, který by potřeboval analýzu, ale analyzátor nezná dané slovo.
                        # Zkusme aspoň bez závislost na slovním druhu (protože ho nezjistíme) otestovat slovo na ženská koncovky.
                        if token.word[-3:] in {"ová", "cká", "ská"}:
                            # muž s přijmení končícím na ová,cká a ská, zřejmě není
                            # změníme typ pokud není ženský
                            changeTo = self.Type.PersonGender.FEMALE
                        break

            # Provedeme odhad na základě gramatik, pokud bude odpovídat právě jedna gramatika, pak ji přířazený typ
            # určuje daný odhad.
            aTokens = None
            rules = None

            if changeTo is None and grammars:
                for t, g in grammars.items():
                    try:
                        rules, aTokens = g.analyse(tokens)

                        if changeTo is None:
                            # zatím odpovídá jedna gramatika
                            changeTo = t
                        else:
                            # více než jedna gramatika odpovídá
                            changeTo = None
                            aTokens = None
                            rules = None
                            break

                    except namegenPack.Grammar.Grammar.NotInLanguage:
                        continue

            # Vytvoříme si příznak pro smazání derivací, protože dále klademe další podmínky, které musí být splněny.
            # pokud nebudou smažeme derivace před návratem z funkce.
            cleanDeriv = True

            if changeTo is not None:

                if self._type == None:   #Používáme rozšířené porovnání implementované v Name.__eq__.
                    logging.info("Pro " + str(self) + " přiřazuji " + str(changeTo) + ".")
                    if self._type is None:
                        # Nutné vytvořit celý nový typ.
                        # Formát pro osoby:
                        # <Type: P=Person>:<Subtype: F/G=Fictional/Group>:<Future purposes: determine regular name and alias>:<Gender: F/M=Female/Male>
                        self._type = self.Type("P:::" + str(changeTo))
                    else:
                        # Stačí jen doplnit gender
                        self._type.levels[self.Type.INDEX_OF_PERSONS_GENDER] = changeTo

                    cleanDeriv = False  # tyto derivace chceme použít

                else:
                    if self._type.levels[self.Type.INDEX_OF_PERSONS_GENDER] != changeTo and aTokens is not None:
                        couldNotChange = False  # příznak, že se druh nemůže změnit
                        if self._language.code == "cs":
                            # pro češtinu klademe tvrdší podmínky při změně
                            # Změníme typ pouze pokud morfologická analýza říká, že daná slova opravdu mohou být G či S.
                            # Tedy například pokud gramatika říká, že dané slovo má být příjmení, tak morfologický analyzátor
                            # musí dané příjmení jako příjmení znát (note=jS).

                            for actDerivAnalTokens in aTokens:

                                for aT in actDerivAnalTokens:

                                    # získejme prvně druh slova ve jméně

                                    wordType = aT.matchingTerminal.getAttribute(
                                        namegenPack.Grammar.Terminal.Attribute.Type.WORD_TYPE)

                                    if wordType.value in {WordTypeMark.GIVEN_NAME, WordTypeMark.SURNAME}:
                                        # kontrolujeme jen pro jméno a příjmení

                                        if aT.token.type == namegenPack.Grammar.Token.Type.ANALYZE_UNKNOWN:
                                            # budeme provádět změnu jen v případech, kdy máme pro všechna zkoumaná slova potřebnou analýzyu
                                            couldNotChange = True
                                            break

                                        # podmínky na slovo, které budou použity při generování tvarů
                                        # použijeme
                                        conditionWord = aT.morphCategories

                                        # zjistíme jaké máme poznámky
                                        notes = aT.token.word.info.getAllForCategory(MorphCategories.MorphCategories.NOTE,
                                                                                     conditionWord)

                                        if (Note.GIVEN_NAME if wordType.value == WordTypeMark.GIVEN_NAME else Note.SURNAME) not in notes:
                                            # nemáme přislušnou poznámku v morfologické analýze nemůžeme tedy druh změnit
                                            couldNotChange = True
                                            break
                                if couldNotChange:
                                    break

                        if not couldNotChange:
                            logging.info("Pro " + str(self) + " měním " + str(
                                self._type.levels[self.Type.INDEX_OF_PERSONS_GENDER]) + " na " + str(changeTo) + ".")
                            self._type.levels[self.Type.INDEX_OF_PERSONS_GENDER] = changeTo
                            cleanDeriv = False  # tyto derivace chceme použít

        except Word.WordCouldntGetInfoException:
            # nepovedlo se získat informace o slově
            # končíme
            return

        if cleanDeriv:
            rules = None
            aTokens = None

        return rules, aTokens

    @property
    def words(self):
        """
        Slova tvořící jméno.

        @return: Slova ve jméně
        @rtype: List[Word]
        """

        return self._words

    @words.setter
    def words(self, newWords: List[Word]):
        """
        Přiřadí nové slova do jména.
        Používat obezřetně. Dojde opravdu jen k náhradě slov, sepárotory zůstavají.

        :param newWords: Nová slova ve jméně.
        :type newWords:List[Word]
        """

        self._words=newWords

    @property
    def separators(self):
        """
        Oddělovače ve jméně.
        @return: Oddělovače ve jméně
        @rtype: list
        """

        return self._separators

    @staticmethod
    def _findWords(name):
        """
        Získání slov a oddělovačů v daném slově.

        :param name: Daný název.
        :type name: String
        :return: Dvojici se slovy a oddělovači.
        """

        words = []
        separators = []

        actWord = ""
        actSeparator = ""
        separatorOccured = False

        parsingNumeric = False  # Chceme i rozdělovat slova jako: 1.díl (Jako např. v názvu Škarez 1.díl )

        # Procházíme jméno a hledáme slova s jejich oddělovači.
        # Vynacháváme oddělovače na konci a začátku.
        for offsetC, c in enumerate(name):
            if Name.isSeparator(c):
                # separátor

                if len(actWord) > 0:
                    # počáteční vynecháváme
                    actSeparator += c
                    separatorOccured = True

                parsingNumeric = False  # budeme delit tak, ci tak
            else:
                # znak slova

                if c.isnumeric():
                    # slovo obsahuje cislici, budeme chtit pripadne delit
                    # a pokud mame co, tak budeme delit jiz hned
                    if len(actWord) > 0 and not parsingNumeric:
                        # pred cislici byly nejake znaky (ne cislice)
                        separatorOccured = True

                    parsingNumeric = True
                elif parsingNumeric and c != ".":
                    # budeme delit
                    separatorOccured = True
                    parsingNumeric = False
                elif c == "." and not parsingNumeric and (offsetC+1 < len(name) and not Name.isSeparator(name[offsetC+1])):
                    # tečka na konci slova, které není číslicí a nestoji před separátorem
                    actWord += c
                    separatorOccured = True
                    c = ""

                if separatorOccured:
                    # již se má načítat další slovo
                    # uložíme to staré a příslušný separátor
                    words.append(actWord)
                    actWord = ""

                    separators.append(actSeparator)
                    actSeparator = ""
                    separatorOccured = False

                actWord += c

        if len(actWord) > 0:
            words.append(actWord)

        return words, separators

    @staticmethod
    def isSeparator(c: str) -> bool:
        """
        Checks if character c is separator.

        :param c: The char you want to check.
        :type c: str
        :return: True separator. False otherwise.
        :rtype: bool
        """

        return c.isspace() or c == '-' or c == '–' or c == ','

    def simpleWordsTypesGuess(self, tokens: List[namegenPack.Grammar.Token] = None):
        """
        Provede zjednodušený odhad typů slov ve jméně.

        :param tokens: Tokeny odpovídající tomuto jménu. Tento volitelný parametr je zde zaveden pro zrychlení výpočtu, aby nebylo nutné v některých případech
            provádět vícekrát lexikální analýzu. Pokud bude vynechán nic se neděje jen si provede lexikální analýzu sám.
        :type tokens: List[Token]
        :return: Typy pro slova ve jméně.
        :rtype: List(namegenPack.Word.WordTypeMark)
        """

        if not tokens:
            tokens = self.language.lex.getTokens(self)

        types = []
        logging.info(str(self) + "\tPoužívám zjednodušené určování druhu slov.")

        if len(tokens) == 2:
            # jednoslovné
            if self.Type.INDEX_OF_FUTURE_PURPOSES < len(self._type.levels) \
                    and self._type.levels[self.Type.INDEX_OF_FUTURE_PURPOSES] in {"N", "P"}:
                # jednoslovný alias
                types.append(namegenPack.Word.WordTypeMark.ALIAS)
        elif len(tokens) == 3:
            #dvojslovné
            if (self._type == self.Type.PersonGender.FEMALE or self._type == None) and self._words[-1][-3:] == "ová":
                # ženské dvojslovné jméno končící na ová
                types.append(namegenPack.Word.WordTypeMark.GIVEN_NAME)
                types.append(namegenPack.Word.WordTypeMark.SURNAME)

        types.append(None)  # koncový terminál

        if len(types) != len(tokens):
            # no simple guess available
            types = [namegenPack.Word.WordTypeMark.UNKNOWN] * len(tokens)

        return types

    def genMorphs(self, analyzedTokens: List[namegenPack.Grammar.AnalyzedToken],
                  missingCaseToken: Set[Tuple[namegenPack.Grammar.AnalyzedToken, Case]] = None):
        """
        Na základě slovům odpovídajících analyzovaných tokenů ve jméně vygeneruje tvary jména.
        Pokusí se vygenerovat všech sedm pádů, pokud nebude možné nějaké vygenerovat vrátí alespoň ty, které
        se mu vygenerovat povedly.

        :param analyzedTokens: Analyzované tokeny, získané ze syntaktické analýzy tohoto jména.
        :type analyzedTokens: List[namegenPack.Grammar.AnalyzedToken]
        :param missingCaseToken: Volitelný atribut, který lze použít pro získání tokenú/slov, u kterých se nepodařilo
            získat tvar v nějakém z pádů.
        :type missingCaseToken: Set[Tuple[AnalyzedToken, Case]]
        :return:  Vygenerované tvary pro každý pád. Seřazeno od 1. pádu do 7..
        :rtype: List[NameMorph]
        :raise Word.WordNoMorphsException: Pokud se nepodaří získat tvary u nějakého slova.
        :raise WordCouldntGetInfoException: Vyjímka symbolizující, že se nepovedlo získat mluvnické kategorie ke slovu.
        """

        # získáme tvary jednotlivých slov
        genMorphsForWords = []
        for word, aToken in zip(self._words, analyzedTokens):
            if aToken.morph:
                cateWord = aToken.morphCategories  # podmínky na původní slovo

                cateMorph = set()  # podmínky přímo na tvary
                # překopírujeme a ignorujeme pády, jelikož nemůžeme vybrat jen jeden, když chceme
                # generovat všechny
                for x in cateWord:
                    if x.category() != MorphCategories.MorphCategories.CASE:
                        cateMorph.add(x)

                # ještě získáme flagy, pro filtraci
                groupFlags = aToken.matchingTerminal.getAttribute(Terminal.Attribute.Type.FLAGS)
                groupFlags = set() if groupFlags is None else groupFlags.value

                genMorphsForWords.append(word.morphs(cateMorph, cateWord, groupFlags))

            else:
                genMorphsForWords.append(None)

        # z tvarů slov poskládáme tvary jména
        # Set[Tuple[MARule,str]]
        morphs = []

        if self.grammar.flexible:
            cases = [Case.NOMINATIVE, Case.GENITIVE, Case.DATIVE, Case.ACCUSATIVE, Case.VOCATIVE, Case.LOCATIVE,
                     Case.INSTRUMENTAL]
        else:
            # neohebná gramatika (angličtina apod.) nechcem další tvary
            cases = [Case.NOMINATIVE]

        for c in cases:  # pády
            wordsTypes=[]
            wordsWithRules=[]
            for i, (word, aToken) in enumerate(zip(self._words, analyzedTokens)):

                if aToken.morph and isinstance(genMorphsForWords[i], set):
                    # ohýbáme

                    morphsThatWeAlreadyHaves = set()

                    morphsWithRules=set()

                    for maRule, wordMorph in genMorphsForWords[i]:
                        # najdeme tvar slova pro daný pád
                        try:
                            if maRule[MorphCategories.MorphCategories.CASE] == c:
                                actMorph = wordMorph + "[" + maRule.lntrfWithoutNote + "]"

                                if actMorph in morphsThatWeAlreadyHaves:
                                    # Díky tomu, že nezohledňujeme poznámku při výpisu,
                                    # tak můžeme dostávat tvary, které vypadají totožně a není
                                    # nutné je tedy vypisovat.
                                    continue

                                morphsThatWeAlreadyHaves.add(actMorph)
                                morphsWithRules.add((wordMorph, maRule))


                        except KeyError:
                            # pravděpodobně nemá pád vůbec
                            pass

                    if len(morphsWithRules)==0:
                        # nepovedlo se získat aktuální pád pro aktuální slovo
                        if missingCaseToken is not None:
                            missingCaseToken.add((aToken, c))
                    else:
                        wordsWithRules.append(morphsWithRules)
                        wordsTypes.append((aToken.matchingTerminal.getAttribute(
                            namegenPack.Grammar.Terminal.Attribute.Type.WORD_TYPE).value, False))
                else:
                    # neohýbáme
                    wordsWithRules.append({(str(word), None)})
                    wordsTypes.append((aToken.matchingTerminal.getAttribute(
                        namegenPack.Grammar.Terminal.Attribute.Type.WORD_TYPE).value,
                               aToken.token.type == Token.Type.ANALYZE_UNKNOWN))

            if len(wordsWithRules) == len(self._words):
                # máme tvar pro všechna slova
                morphs.append(NameMorph(self, wordsWithRules, wordsTypes))

            if not self.grammar.flexible:
                # neohebná gramatika (angličtina apod.) nechcem další tvary
                missingCaseToken.clear()
                break

        return morphs

    @staticmethod
    def getWordsOfType(wordType: WordTypeMark, analyzedTokens: List[namegenPack.Grammar.AnalyzedToken]):
        """
        Na základě slovům odpovídajících analyzovaných tokenů ve jméně vybere slova daného typu.

        :param wordType: Druh slova na základě, kterého vybírá
        :type wordType: WordTypeMark
        :param analyzedTokens: Analyzované tokeny, získané ze syntaktické analýzy tohoto jména.
        :type analyzedTokens: List[namegenPack.Grammar.AnalyzedToken]
        :return: List s vybranými slovy a příslušnými značko pravidly.
        :rtype: List[Tuple[Word, Set[MARule]]]
        """
        selection = []
        for aToken in analyzedTokens:
            if aToken.matchingTerminal.getAttribute(
                    namegenPack.Grammar.Terminal.Attribute.Type.WORD_TYPE).value == wordType:
                # získáme příslušná pravidla

                cateFilters = aToken.morphCategories  # podmínky na původní slovo

                rules = {r for r, w in aToken.token.word.morphs(cateFilters, cateFilters) if
                         str(w) == str(aToken.token.word)}
                selection.append((aToken.token.word, {r for r in rules}))

        return selection

    @property
    def type(self):
        """Getter pro druh jména."""
        return self._type

    @property
    def orig_language_code(self):
        """Getter pro originální kód jazyk jména, který byl uveden na vstupu."""
        return self._orig_language_code

    @property
    def language(self):
        """Getter pro jazyk jména."""
        return self._language

    @property
    def grammar(self):
        """Getter pro gramatiku, která odpovídá jazyku a druhu jména."""
        try:
            if self.type == Name.Type.MainType.LOCATION:
                g = self.language.gLocations
            elif self.type == Name.Type.PersonGender.MALE:
                g = self.language.gMale
            elif self.type == Name.Type.PersonGender.FEMALE:
                g = self.language.gFemale
            elif self.type == Name.Type.MainType.EVENTS:
                g = self.language.gEvents
            else:
                # je cosi prohnilého ve stavu tohoto programu
                raise Errors.ExceptionMessageCode(Errors.ErrorMessenger.CODE_ALL_VALUES_NOT_COVERED)

            return g

        except KeyError:
            # je cosi prohnilého ve stavu tohoto programu
            raise Errors.ExceptionMessageCode(Errors.ErrorMessenger.CODE_ALL_VALUES_NOT_COVERED)


class NameReader(object):
    """
    Třída pro čtení vstupního souboru a převedení vstupu do posloupnosti objektů Name.

    """

    def __init__(self, languages: Dict[str, Language], langDef: str, inputFile=None, shouldSort:bool=True):
        """
        Konstruktor

        :param languages: All suported languages.
        :type languages: Dict[str, Language]
        :param langDef: The default language for unknown.
        :type langDef: str
        :param inputFile: Cesta ke vstupnímu souboru se jmény.
            Pokud je None čte z stdin
        :type inputFile: string | None
        :param shouldSort: Příznak zda si má po přečtení uložit jména v sežazeném pořadí vzestupně.
        :type shouldSort: bool
        """
        self.names = []
        self._errorCnt = 0  # počet chybných nenačtených jmen

        if inputFile is None:
            self._readInput(sys.stdin, languages, langDef)
        else:
            with open(inputFile, "r") as rInput:
                self._readInput(rInput, languages, langDef)

        if shouldSort:
            self.sortNames()

    def sortNames(self):
        """
        Performs sorting of all names.
        """

        self.names = sorted(self.names)

    def _readInput(self, rInput, languages: Dict[str, Language], langDef: str):
        """
        Čtení vstupu.

        :param rInput: Vstup
        :param languages: All suported languages.
        :param langDef: The default language for unknown.
        """

        for line in rInput:
            line = line[:-1].lstrip()
            parts = line.split("\t")  # <jméno>\TAB<jazyk>\TAB<typeflag>\TAB<url>

            if len(parts) < 3:
                # nevalidní formát vstupu
                print(Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_INVALID_NAME) + "\t" + line,
                      file=sys.stderr)
                self._errorCnt += 1
                continue
            try:
                additInfo = []  # přídavné info, například URL odkaď název/jméno pochází
                if len(parts) > 3:
                    additInfo = parts[3:]
                # <jméno>\TAB<jazyk>\TAB<typeflag>\TAB<url>

                lang = langDef if parts[1] == "" else parts[1]

                try:
                    lang = languages[lang]
                except KeyError:
                    lang = None

                self.names.append(Name(parts[0], parts[1], lang, parts[2], additInfo))
            except Name.NameCouldntCreateException as e:
                # problém při vytváření jména
                print(e.message, file=sys.stderr)
                self._errorCnt += 1

    @property
    def errorCnt(self):
        """
        Počet chybných nenačtených jmen
        """
        return self._errorCnt

    def allWords(self, alnumCheck: bool = False) -> Set[Word]:
        """
        Slova vyskytující se ve všech jménech.

        :param alnumCheck: Vybere jen ta slova, která obsahují aspoň jeden alfanumerický znak.
        :return Množina všech slov ve jménech.
        """
        words = set()

        if alnumCheck:
            for name in self.names:
                for w in name:
                    if any(s.isalnum() for s in str(w)):
                        words.add(w)
        else:
            for name in self.names:
                for w in name:
                    words.add(w)
        return words

    def __iter__(self):
        """
        Iterace přes všechna jména. V seřazeném pořadí.
        """
        return iter(self.names)

    def filter(self, useF: Filter, printFiltered: Optional[TextIO] = None):
        """
        Profiltruje načtená jména pomocí zvoleného filtru.

        :param useF: Filtr, který mý být použit.
        :param printFiltered: Vytiskne dané jméno do tohoto souboru/TextIO, pokud bude odfiltrováno.
        Jinak pouze oznámí do logu.
        """


        filteredNames = []
        for name in self:

            if useF(name):
                filteredNames.append(name)
            else:
                # Na základě uživatelských filtrů nemají být pro toto jméno
                # generovány tvary.

                logging.info("Neprošlo filtrem: " + str(name))

                if printFiltered is not None:
                    print(name.printName(), file=printFiltered)

                continue

        self.names = filteredNames



