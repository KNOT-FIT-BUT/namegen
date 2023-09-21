"""
Created on 14. 7. 2018

Tento modul obsahuje třídy pro morfologickou analýzu.

:author:     Martin Dočekal
:contact:    xdocek09@stud.fit.vubtr.cz
"""

import collections
import logging
import math
import string
from abc import ABC, abstractmethod
from copy import copy
from subprocess import Popen, PIPE
from typing import Set, Dict, Tuple, Optional, List

from namegenPack.morpho.MorphCategories import *
from ..Errors import ExceptionMessageCode, ErrorMessenger


class MARule(collections.Mapping):
    """
    Reprezentace pravidla tvaru z morfologické analýzy.
    Pravidlo reprezentuje mluvnické kategorie, které ma dané slovo.
    """

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __hash__(self):
        if self._hash is None:
            self._hash = 0
            for pair in self._d.items():
                self._hash ^= hash(pair)
        return self._hash

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return repr(self._d)

    def sameExcept(self, other, exceptCat: Set[MorphCategories] = None):
        """
        Porovnává aktuální pravidlo s nějakým jiným zdali je stejné až na dané morfologické kategorie.

        !!! V případě více hodnotových morfologických kategorií se považují kategorie u daných pravidel za stejné
        majíly neprázdný průnik nebo jsou obě prázdné.
        
        :param other: Pravidlo pro porovnání.
        :type other: MARule
        :param exceptCat: Kategorie, které nejsou zohledňovány při kontrole na shodu.
        :type exceptCat: Set[MorphCategories]
        """
        if exceptCat is None:
            exceptCat = set()

        try:
            for morphCat, morphCatVal in self.items():
                if morphCat not in exceptCat:
                    # kontrolujeme jen ty kategorie, které chceme

                    if isinstance(other[morphCat], frozenset) and isinstance(morphCatVal, frozenset):
                        # více hodnotové atributy
                        if (len(morphCatVal) > 0 or len(other[morphCat]) > 0) and len(
                                morphCatVal & other[morphCat]) == 0:
                            # Kategorie mají prázdný průnik a nejsou obě prázdné.
                            return False
                    else:

                        if other[morphCat] != morphCatVal:
                            # nemá stejnou hodnotu pro morphcat
                            return False
        except KeyError:
            # asi nemá morphCat vůbec
            return False

        return True

    def fitsToFilters(self, valFilter: Set[MorphCategory] = None,
                      notValFilter: Set[MorphCategory] = None, valFilterUsedCategories: Set[MorphCategories] = None):
        """
        Detekce zdali pravidlo padne na poskytnuté filtry
        
        :param valFilter: (Volitelný) Filtr, který určuje pevně stanovené 
                hodnoty, které musí mít pravidlo, aby se vrátilo True.
                Tedy není-li v daném pravidle vůbec zminěná kategorie obsažena, tak pravidlo neprojde přes filtr.
        :type valFilter: Set[MorphCategory]
        :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo obsahovat.
        :type notValFilter:Set[MorphCategory]
        :param valFilterUsedCategories: Tento parametr lze použít pro urychlení aplikování filtru. Přeskočí se fáze získávání morfologických kategorií
            z hodnot ve valFilter.
        :type valFilterUsedCategories: Set[MorphCategories]
        :return: Vrácí True pokud pravidlo projde přes dané filtry.
        :rtype: bool
        """
        if valFilter is None:
            valFilter = set()
        if notValFilter is None:
            notValFilter = set()

        if valFilterUsedCategories is None:
            valFilterUsedCategories = {f.category() for f in valFilter}

        try:
            # Kategorie pravidla může obsahovat přímo hodnotu nebo množinu hodnot.
            # Musíme se tedy rozhodnout zdali budeme danou kategorii pravidla zpracovávat jako množinu nebo hodnotu,

            if all(self._categoryValFilter(c, valFilter) for c in valFilterUsedCategories):
                # Máme splněny všechny valFilter podmínky.

                # Ted se mrkneme na notValFilter podmínky.
                for forbidden in notValFilter:
                    if forbidden.category() in self:
                        if isinstance(self[forbidden.category()], frozenset):
                            if forbidden in self[forbidden.category()]:
                                return False
                        else:
                            if self[forbidden.category()] == forbidden:
                                return False

                # vše ok
                return True

        except KeyError:
            pass

        return False

    def _categoryValFilter(self, category: MorphCategories, valFilter: Set[MorphCategory]):
        """
        Zjistí zdali daná kategorie v pravidle obsahuje pouze hodnoty z valFilter.

        :param category: Morfologická kategorie pravidla, kterou chceme prozkoumat.
        :type category: MorphCategories
        :param valFilter: Hodnoty, které jsou povoleny.
        (Může obsahovat klidně i další hodnoty z jiných kategorii.)
        :type valFilter: Set[MorphCategory]
        :return: True pokud je filter splněn. Flase jinak.
        :rtype bool
        """

        if isinstance(self[category], frozenset):
            return any(v in valFilter for v in self[category])
        else:
            return self[category] in valFilter

    @property
    def lntrf(self):
        """
        Ve formátu lntrf. Včetně poznámky
        """
        res = self.lntrfWithoutNote
        try:
            return res + "".join(note.lntrf for note in self[MorphCategories.NOTE])
        except KeyError:
            pass
        return res

    @property
    def lntrfWithoutNote(self):
        """
        Ve formátu lntrf. Bez poznámky
        """

        try:
            pos = self[MorphCategories.POS].lntrf
            # pořadí pro ify je voleno dle předpokládané četnosti
            if self[MorphCategories.POS] == POS.NOUN:
                # podstané jméno zjistím rod, číslo, pád
                pos += self[MorphCategories.GENDER].lntrf \
                       + self[MorphCategories.NUMBER].lntrf \
                       + self[MorphCategories.CASE].lntrf

            elif self[MorphCategories.POS] == POS.ADJECTIVE:
                # přídavné jméno zjistím negaci,rod, číslo, pád, stupeň
                pos += self[MorphCategories.NEGATION].lntrf \
                       + self[MorphCategories.GENDER].lntrf \
                       + self[MorphCategories.NUMBER].lntrf \
                       + self[MorphCategories.CASE].lntrf \
                       + self[MorphCategories.DEGREE_OF_COMPARISON].lntrf
            elif self[MorphCategories.POS] == POS.NUMERAL:
                # číslovka rod, číslo, pád
                pos += self[MorphCategories.GENDER].lntrf \
                       + self[MorphCategories.NUMBER].lntrf \
                       + self[MorphCategories.CASE].lntrf

            elif self[MorphCategories.POS] == POS.PRONOUN:
                # zájméno zjistime rod, číslo, pád
                pos += self[MorphCategories.GENDER].lntrf \
                       + self[MorphCategories.NUMBER].lntrf \
                       + self[MorphCategories.CASE].lntrf

            elif self[MorphCategories.POS] == POS.VERB:
                # sloveso negace, osoba, číslo
                pos += self[MorphCategories.NEGATION].lntrf \
                       + self[MorphCategories.PERSON].lntrf \
                       + self[MorphCategories.NUMBER].lntrf

            elif self[MorphCategories.POS] == POS.ADVERB:
                # příslovce negace stupeň
                pos += self[MorphCategories.NEGATION].lntrf \
                       + self[MorphCategories.DEGREE_OF_COMPARISON].lntrf

            """ PRO PŘÍPADNÉ BUDOUCÍ UŽITÍ

            elif self[MorphCategories.POS] == POS.PREPOSITION:
                # předložka pád
                pass

            elif self[MorphCategories.POS] == POS.PREPOSITION_M:
                # předložka M pád
                pass

            elif self[MorphCategories.POS] == POS.CONJUNCTION:
                # spojka, nic
                pass

            elif self[MorphCategories.POS] == POS.PARTICLE:
                # částice, nic
                pass
            elif self[MorphCategories.POS] == POS.INTERJECTION:
                # citoslovce, nic
                pass
            """
            # nakonec přidáme stylistický příznak, pokud existuje.
            if MorphCategories.STYLISTIC_FLAG in self:
                pos += self[MorphCategories.STYLISTIC_FLAG].lntrf

            return pos
        except KeyError:
            # zdá se, že nevyhovuje tradičnímu rozvržení
            # zkusíme tedy co všechno má
            res = ""

            for x in [MorphCategories.POS, MorphCategories.NEGATION, MorphCategories.GENDER, MorphCategories.PERSON,
                      MorphCategories.NUMBER, MorphCategories.CASE, MorphCategories.NEGATION,
                      MorphCategories.DEGREE_OF_COMPARISON, MorphCategories.STYLISTIC_FLAG]:
                try:
                    res += self[x].lntrf
                except KeyError:
                    # tohle ne zkusíme další
                    pass

            return res


class MorphoAnalyze(ABC):
    """
    Interface pro výsledky morfologické analýzy slova.
    """

    @abstractmethod
    def getAll(self, valFilter: Set[MorphCategory] = None, notValFilter: Set[MorphCategory] = None,
               groupFlags: Set[Flag] = None) -> Dict[MorphCategories, Set[MorphCategory]]:
        """
        Vrácení všech možných hodnot mluvnických kategorií.
        
        :param valFilter: (Volitelný) Filtr, který určuje pevně stanovené 
            hodnoty, které musí mít dané pravidlo, aby se bralo v úvahu.
            Tedy není-li v daném pravidle vůbec zmíněná kategorie obsažena, tak pravidlo neprojde přes filtr.
            Příklad: Chci získat všechny rody jakých může nabývat slovo pokud je podstatným jménem.
            Nastavím filtr na: set(POS.NOUN)
            Chci získat všechny hodnoty pro slovo ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
        :type valFilter: Set[MorphCategory]
        :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
        :type notValFilter:Set[MorphCategory]
        :param groupFlags: Flagy, které musí mít daná skupina vázající se na slovo.
        :type groupFlags: Set[Flag]
        :return: Hodnoty mluvnických kategorií.
        :rtype: Dict[MorphCategories, Set[MorphCategory]]
        """
        pass

    @abstractmethod
    def getAllForCategory(self, morphCategory: MorphCategories, valFilter: Set[MorphCategory] = None,
                          notValFilter: Set[MorphCategory] = None, groupFlags: Set[Flag] = None) -> Set[MorphCategory]:
        """
        Vrácení všech možných hodnot dané mluvnické kategorie.
        
        :param morphCategory: Mluvnická kategorie.
        :type morphCategory: MorphCategories
        :param valFilter: (Volitelný) Filter, který určuje pevně stanovené 
            hodnoty, které musí mít dané pravidlo, aby se bralo v úvahu.
            Tedy není-li v daném pravidle/rozboru vůbec zminěná kategorie obsažena, tak pravidlo neprojde přes filtr.
            Příklad: Chci získat všechny rody jakých může nabývat slovo pokud je podstatným jménem.
            Nastavím filtr na: set(POS.NOUN)
            Chci získat všechny hodnoty pro slovo ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
        :type valFilter: Set[MorphCategory]
        :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
        :type notValFilter:Set[MorphCategory]
        :param groupFlags: Flagy, které musí mít daná skupina vázající se na slovo.
        :type groupFlags: Set[Flag]
        :return: Hodnoty dané mluvnické kategorie.
        :rtype: Set[MorphCategory]
        """
        pass

    @abstractmethod
    def getMorphs(self, valFilter: Set[MorphCategory] = None, notValFilter: Set[MorphCategory] = None,
                  wordFilter: Set[MorphCategory] = None, groupFlags: Set[Flag] = None) -> Set[Tuple[MARule, str]]:
        """
        Získání tvarů.
        
        :param valFilter: (Volitelný) Filtr, který určuje pevně stanovené 
                hodnoty, které musí mít pravidlo tvaru, aby se bral v úvahu daný tvar.
                Tedy není-li v daném pravidle tvaru vůbec zminěná kategorie obsažena, tak tvar neprojde přes filtr.
                Příklad: Chci získat všechny tvary, které jsou podstatným jménem, tak
                nastavím filtr na: set(POS.NOUN)
                Chci získat všechny tvary ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
        :type valFilter: Set[MorphCategory]
        :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
        :type notValFilter:Set[MorphCategory]
        :param wordFilter: Podmínky na původní slovo. Jelikož analýza nám může říci několik variant, tak tímto filtrem můžeme
            spřesnit odhad.
            Chceme-li získat všechny tvary, které se váží na případy, kdy se předpokládá, že původní slovo mělo
            danou morfologickou kategorii, tak použijeme tento filtr.
                Příklad: Pokud je vložen 1. pád. Budou brány v úvahu jen tvary, které patří ke skupině tvarů vázajících se na případ
                že původní slovo je v 1. pádu.
        :type wordFilter: Set[MorphCategory]
        :param groupFlags: Flagy, které musí mít daná skupina vázající se na slovo.
        :type groupFlags: Set[Flag]
        :return: Množinu dvojic (pravidlo, tvar).
        :rtype: Set[Tuple[MARule,str]]
        """
        pass


class MorphoAnalyzer(ABC):
    """
    Interface morfologického analyzátoru.
    """

    @abstractmethod
    def isNameDependant(self, word: str, name) -> bool:
        """
        Zjistí zdali daná kombinace slova a jména má na jméně závislou analýzu.

        :param word: slovo pro analýzu
        :type word: str
        :param name: Celé jméno v němž je předané slovo obsaženo.
        :type name: Name
        :return: True -> Slovo má na jméně závislou analýzu.
                False -> nemá
        :rtype: bool
        """
        pass

    @abstractmethod
    def analyze(self, word: str, name=None, wordPos: Optional[int]=None) -> MorphoAnalyze:
        """
        Získání morfologické analýzy slova.

        :param word: slovo pro analýzu
        :type word: str
        :param name: Pokud je tento parametr neprázdný pak provede analýzu slova závislou na předaném jménu.
        :type name: Name
        :param wordPos: Pozice slova ve jméně.
        :type wordPos: Optional[int]
        :return: Analýza slova. None při neúspěchu.
        :rtype: MorphoAnalyze
        """
        pass


class EQRelationForPrepAndItsAbbre(object):
    """
    Implementace relace ekvivalence:
        Bernstadt auf dem Eigen <->  Bernstadt a. d. Eigen
    """

    def __init__(self, name):
        """
        Vytvoření objektu implementujícího relaci ekvivalence.

        :param name: Relace je tvořena pro toto jméno.
        :type name: Name
        """
        self.name = name

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            if len(self.name) == len(other.name) and self.name[0] == other.name[0] and \
                    self.name[-1] == other.name[-1]:
                # Jména jsou stejně dlouhé mají stejná první a poslední slova,
                # ted se pojďme podívat ještě na korespondence typu:
                # Bernstadt auf dem Eigen <->  Bernstadt a. d. Eigen

                # prohledáváme prostřední slova
                constraintAllCor = True  # všechny prostřední slova musí koresponovat
                constraintAtLeastOneAbber = False  # je mezi nimi alespoň jedno slovo připomínající zkratku.
                for wI in range(1, len(self.name) - 1):
                    if self.name[wI][0] == other.name[wI][0]:

                        # máme shodu na první písmeno
                        if len(self.name[wI]) == 2 and self.name[wI][-1] == "." and self.name[wI][-2].islower():
                            # actName je zkratka korespondující s curCheckingName
                            constraintAtLeastOneAbber = True
                        elif len(other.name[wI]) == 2 and \
                                other.name[wI][-1] == "." and other.name[wI][-2].islower():
                            # curCheckingName je zkratka korespondující s actName
                            constraintAtLeastOneAbber = True
                        elif self.name[wI] != other.name[wI]:
                            # neshodují se a nejedná se o zkratku
                            constraintAllCor = False
                    else:
                        # neshodují se
                        constraintAllCor = False
                        break

                return constraintAllCor and constraintAtLeastOneAbber

        return False

    def __hash__(self):
        # hashujeme 1. a poslední slovo ve jménu, protože ta se musí shodovat přesně.
        # Stejně, tak hashujeme společně s nimi délku jména, která musí být taktéž shodná.
        return hash((str(self.name[0]) + str(self.name[-1]), str(len(self.name))))


class MorphoAnalyzerException(ExceptionMessageCode):
    """
    Vyjímka pro problémy s morfologickým analyzátorem
    """
    pass


class MorphoAnalyzerLibma(MorphoAnalyzer):
    """
    Obálka pro Morfologický analyzátor postavený na knihovně libma
    .. _ma: http://knot.fit.vutbr.cz/wiki/index.php/Morfologický_slovník_a_morfologický_analyzátor_pro_češtinu

    """

    class MAWordGroup(object):
        """
        Třída reprezentující skupinu slov k nějakému slovu.
        Obsahuje lemma a vzor daného slova. Také značko-pravidla pro dané slovo
        a různé tvary společně s jejich značko pravidly.

        Libma dělí analýzu slova na více skupin. Tato třída reprezentuje jednu ze skupin.
        Zkrácený příklad pro slovo Velké (skupina začíná <s>):
        ma><s> Velké (Sedláčková_nF)
          <l>Velká
          <c>k1gFnPc1
          <c>k1gFnPc4
          ...
          <f>[k1gFnSc7] Velkou
          <f>[k1gFnSc4] Velkou
          <f>[k1gFnSc5] Velká
          <f>[k1gFnSc1] Velká
          <f>[k1gFnSc6] Velké
          <f>[k1gFnSc3] Velké
          ...
        <s> Velké (Široký_nM)
          <l>Velký
          <c>k1gMnPc4
          <f>[k1gMnPc5] Velcí
          <f>[k1gMnPc1] Velcí
          <f>[k1gMnPc4] Velké
          ...
        <s> Velké (velký)
          <l>velký
          <c>k2eAgFnPc1d1
          <c>k2eAgFnPc4d1
          <c>k2eAgFnPc5d1
          ...
          <f>[k2eNgNnPc4d3wH] nejnevětši
          ...
        <s> Karel (cihla)
          <l>Karla jG
          <c>k1gFnPc2;jG
          <f>[k1gFnPc1;jG] Karly
          <f>[k1gFnPc2;jG] Karel
          <f>[k1gFnPc3;jG] Karlám
          ...
          <d>[1201] Karlin (matčin)
        Karlin     Karlina    Karlini    Karlino    Karlinou   Karlinu    Karliny
        Karliných Karliným  Karlinýma Karlinými Karlině
        """

        def __init__(self, word):
            """
            Vytvoření skupiny pro slovo.

            :param word: Slovo pro nějž je tato skupina vytvořena.
            :type word: str
            """
            self._word = word
            self._flags = {Flag.NOT_GENERAL_WORD}  # implicitně se nejedná o obecné slovo
            self._tagRules = []  # značko pravidla pro slovo
            self._morphs = []  # tvary k danému slovu ve formátu dvojic (tagRule, tvar)
            self._derivations = []  # odvozená slova

        @property
        def flags(self):
            """
            Flagy skupiny.
            """
            return self._flags

        def addFlag(self, flag: Flag):
            """
            Přidání flagu ke skupině.
            Stará se o odstraňování flagů, které jsou opakem práve přidaného flagu.
            Příklad:
                Přidávám: Flag.GENERAL_WORD
                Pokud má flag Flag.NOT_GENERAL_WORD, tak bude Flag.NOT_GENERAL_WORD odstraněn.

            :param flag: Nový flag.
            :type flag: Flag
            """
            if flag == Flag.GENERAL_WORD and Flag.NOT_GENERAL_WORD in self._flags:
                self._flags.remove(Flag.NOT_GENERAL_WORD)
            elif flag == Flag.NOT_GENERAL_WORD and Flag.GENERAL_WORD in self._flags:
                self._flags.remove(Flag.GENERAL_WORD)

            self._flags.add(flag)

        def removeFlag(self, flag: Flag):
            """
            Odstranění flagu ze skupině.

            :param flag: Flag pro odstranění.
            :type flag: Flag
            """
            self._flags.remove(flag)

        @property
        def word(self):
            """
            Slovo pro nějž je tato skupina vytvořena.
            """
            return self._word

        @word.setter
        def word(self, value):
            """
            Nastavení slova pro nějž je tato skupina vytvořena.

            :param value: Slovo pro nějž je tato skupina vytvořena.
            :type value: str
            """
            self._word = value

        def addMorph(self, tagRule, morph, relevant=False):
            """
            Přidání tvaru.
            !!!NA ZÁKLADĚ POKYNŮ NEJSOU PŘÍJMÁNY VŠECHNY HOVOROVÉ TVARY

            :param tagRule: Značko pravidlo pro tvar (příklad k1gFnSc7)
            :type tagRule: str
            :param morph: Tvar slova.
            :type morph: str
            :param relevant: Pokud je true, tak nepřídá daný tvar, který nevyhovuje přidaným pravidlům.
                Tvar nevyhovuje přidaným pravidlům ve skupině, máli jiné hodnoty morfologických kategorií až na
                CASE (pád), pokud máme vícehodnotvé moroflogické kategorie, pak musí mít mezi sebou neprázdný průnik.
                Chceme získávat všechny relevantní tvary.
            :type relevant: bool
            """

            rule = self.convTagRule(tagRule)

            if MorphCategories.STYLISTIC_FLAG in rule and \
                    rule[MorphCategories.STYLISTIC_FLAG] == StylisticFlag.COLLOQUIALLY:
                # nechceme hovorové
                return

            if len(rule) > 0:
                # nechceme prázdná pravidla
                if relevant:
                    # uživatel chce přidat jen relevantní
                    for r in self._tagRules:
                        if r.sameExcept(rule, {MorphCategories.CASE, MorphCategories.STYLISTIC_FLAG}):
                            # je stejné jako alespoň jedno pravidlo
                            self._morphs.append((rule, morph))
                else:
                    self._morphs.append((rule, morph))

        def getMorphs(self, valFilter: Set[MorphCategory] = None, notValFilter: Set[MorphCategory] = None) \
                -> Set[Tuple[MARule, str]]:
            """
            Získání tvarů.

            :param valFilter: (Volitelný) Filtr, který určuje pevně stanovené
                hodnoty, které musí mít pravidlo tvaru, aby se bral v úvahu daný tvar.
                Tedy není-li v daném pravidle tvaru vůbec zminěná kategorie obsažena, tak tvar neprojde přes filtr.
                Příklad: Chci získat všechny tvary, které jsou podstatným jménem, tak
                nastavím filtr na: dict(MorphCategories.POS: set(POS.NOUN))
                Chci získat všechny tvary ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
            :type valFilter: Set[MorphCategory]
            :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
            :type notValFilter:Set[MorphCategory]
            :return: Množinu dvojic (pravidlo, tvar).
            :rtype: Set[Tuple[MARule,str]]
            """

            if valFilter is None:
                valFilter = set()

            if notValFilter is None:
                notValFilter = set()

            morphs = set()
            valFilterCategories = set(f.category() for f in valFilter)

            for r, m in self._morphs:
                try:
                    # zkontrolujeme zdali platí filtry
                    if r.fitsToFilters(valFilter, notValFilter, valFilterCategories):
                        # úprava velikosti počátečního písmene tvaru na základě původního slova
                        if self._word[0].isupper():
                            newM = m[0].upper() + m[1:]
                        else:
                            newM = m[0].lower() + m[1:]

                        morphs.add((r, newM))
                except KeyError:
                    # neobsahuje danou mluvnickou kategorii
                    pass

            return morphs

        @staticmethod
        def convTagRule(tagRule):
            """
            Převod značko pravidla ze str do MARule

            :param tagRule: Značko pravidlo (příklad k1gFnPc1)
            :type tagRule: str
            :return: Převedené pravidlo z morfologické analýzy.
            :rtype: MARule
            """
            # Příklad převodu: k1gFnPc1;jL
            #
            #    {"k":"1","g":"F","n":"P","c":"1","note":"jL"}

            # !!! Pro kategorie s více hodnotami se používá frozenset. Dále v kodu se s tím počítá. !!!
            res = dict()
            notes = None
            rule = tagRule.split(MorphCategories.NOTE.lntrf)  # dělíme řetězec dle značky poznámky

            if len(rule) > 1:
                # Pravidlo obsahuje alespoň jednu poznámku.

                notes = []
                for n in rule[1:]:
                    for chunkOffset in range(0, len(n), 2):
                        notes.append(n[chunkOffset:chunkOffset+2])

            rule = rule[0]

            for i in range(0, len(rule) - 1, 2):
                try:
                    mCategory = MorphCategories.fromLntrf(rule[i])
                    res[mCategory] = mCategory.createCategoryFromLntrf(rule[i + 1])
                except (MorphCategoryInvalidException, MorphCategoryInvalidValueException):
                    # neznámá kategorie, či hodnota kategorie
                    # pravděpodobně se jedná o kategorii, která nás nezajíma
                    # tak to vynecháme
                    pass

            if notes is not None:
                mCategory = MorphCategories.NOTE
                tmpVals = set()
                for note in notes:
                    try:
                        tmpVals.add(mCategory.createCategoryFromLntrf(note))
                    except MorphCategoryInvalidValueException:
                        # neznámá hodnota kategorie/hodnoty
                        # pravděpodobně se jedná o kategorii/hodnoty, která nás nezajíma
                        # tak to vynecháme
                        pass

                if len(tmpVals) > 0:  # Jen neprázdné.
                    res[mCategory] = frozenset(tmpVals)

            return MARule(res)

        def addTagRuleConv(self, tagRule: MARule):
            """
            Přidání značko pravidla, které již bylo zkonvertováno pomocí convTagRule.

            NEPŘÍJMÁ StylisticFlag.COLLOQUIALLY

            :param tagRule: Značko pravidlo
            :type tagRule: MARule
            """
            if MorphCategories.NOTE in tagRule:
                # Zkontrolujeme, zda-li aktuálně vkládané pravidlo nemá poznámku

                if Flag.GENERAL_WORD in self._flags:
                    # pokud ano, tak musíme tento flag odstranit.
                    self._flags.remove(Flag.GENERAL_WORD)
                    # a vrátíme implicitní
                    self._flags.add(Flag.NOT_GENERAL_WORD)

            self._tagRules.append(tagRule)

        def addTagRule(self, tagRule):
            """
            Přidání značko pravidla.

            NEPŘÍJMÁ StylisticFlag.COLLOQUIALLY

            :param tagRule: Značko pravidlo (příklad k1gFnPc1)
            :type tagRule: str
            """
            r = self.convTagRule(tagRule)
            if r:
                self.addTagRuleConv(r)

        def getAll(self, valFilter: Set[MorphCategory] = None, notValFilter: Set[MorphCategory] = None) \
                -> Dict[MorphCategories, Set[MorphCategory]]:
            """
            Vrácení všech možných hodnot mluvnických kategorií.

            :param valFilter: (Volitelný) Filtr, který určuje pevně stanovené
                hodnoty, které musí mít dané pravidlo, aby se bralo v úvahu.
                Tedy není-li v daném pravidle vůbec zmíněná kategorie obsažena, tak pravidlo neprojde přes filtr.
                Příklad: Chci získat všechny rody jakých může nabývat slovo pokud je podstatným jménem.
                Nastavím filtr na: set(POS.NOUN)
                Chci získat všechny hodnoty pro slovo ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
            :type valFilter: Set[MorphCategory]
            :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
            :type notValFilter:Set[MorphCategory]
            :return: Hodnoty mluvnických kategorií.
            :rtype: Dict[MorphCategories, Set[MorphCategory]]
            """

            if valFilter is None:
                valFilter = set()
            if notValFilter is None:
                notValFilter = set()
            values = {}

            valFilterCategories = set(f.category() for f in valFilter)
            for r in self._tagRules:
                try:
                    # zkontrolujeme zdali platí filtry
                    if r.fitsToFilters(valFilter, notValFilter, valFilterCategories):
                        for morphCat, morphCatVal in r.items():
                            try:
                                if isinstance(r[morphCat], frozenset):
                                    # máme množinu hodnot
                                    values[morphCat] |= morphCatVal
                                else:
                                    values[morphCat].add(morphCatVal)
                            except KeyError:
                                # první vložení hodnoty dané kategorie
                                if isinstance(morphCatVal, frozenset):
                                    # máme množinu hodnot
                                    values[morphCat] = set(morphCatVal)
                                else:
                                    values[morphCat] = {morphCatVal}

                except KeyError:
                    # neobsahuje danou mluvnickou kategorii
                    pass

            return values

        def getAllForCategory(self, morphCategory: MorphCategories, valFilter: Set[MorphCategory] = None,
                              notValFilter: Set[MorphCategory] = None) -> Set[MorphCategory]:
            """
            Vrácení všech možných hodnot mluvnické kategorie.

            :param morphCategory: Mluvnická kategorie.
            :type morphCategory: MorphCategories
            :param valFilter: (Volitelný) Filtr, který určuje pevně stanovené
                hodnoty, které musí mít dané pravidlo, aby se bralo v úvahu.
                Tedy není-li v daném pravidle vůbec zminěná kategorie obsažena, tak pravidlo neprojde přes filtr.
                Příklad: Chci získat všechny rody jakých může nabývat slovo pokud je podstatným jménem.
                Nastavím filtr na: set(POS.NOUN)
                Chci získat všechny hodnoty pro slovo ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
            :type valFilter: Set[MorphCategory]
            :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
            :type notValFilter:Set[MorphCategory]
            :return: Hodnoty dané mluvnické kategorie.
            :rtype: Set[MorphCategory]
            """

            if valFilter is None:
                valFilter = set()

            if notValFilter is None:
                notValFilter = set()

            values = set()
            valFilterCategories = set(f.category() for f in valFilter)

            for r in self._tagRules:
                try:
                    # zkontrolujeme zdali platí filtry
                    if r.fitsToFilters(valFilter, notValFilter, valFilterCategories):
                        # Jednotlivé kategorie mohou obsahovat jednu hodnotu nebo množinu hodnot.
                        if isinstance(r[morphCategory], frozenset):
                            # máme množinu hodnot
                            values |= r[morphCategory]
                        else:
                            values.add(r[morphCategory])
                except KeyError:
                    # neobsahuje danou mluvnickou kategorii
                    pass

            return values

        def addDerivation(self, derivation, type: Optional[str]):
            """
            Přidání odvozeného slova.

            :param derivation: Odvozené slovo.
            :type derivation: str
            :param type: Typ odvození.
            :type type: Optional[str]
            """
            self._derivations.append((derivation, type))

        def getDerivations(self) -> List[str]:
            """
            Získání odvozených slov.

            :return: Odvozená slova.
            :rtype: List[str]
            """
            return self._derivations

        @property
        def rules(self):
            """
            Přiřazená pravidla
            """
            return self._tagRules

        def __str__(self):
            s = "Tag rules:\n"
            for tr in self._tagRules:
                s += "\t" + str(tr) + "\n"
            s += "Flags:\n"
            for f in self._flags:
                s += "\t" + str(f) + "\n"
            s += "Morphs:\n"
            for m in self._morphs:
                s += "\t" + str(m[0]) + "\t" + str(m[1]) + "\n"

            return s

    class MAWord(MorphoAnalyze):
        """
        Obsahuje data z morfologické analýzy slova.
        """

        def __init__(self):
            """
            Vytvoření instance morfologické analýzy slova.

            """
            self._groups = []

        def addGroup(self, group):
            """
            Přidání skupiny z morfoligické analýzy.

            :param group: Skupina z analýzy obsahující vzor, lemma, tvary, značko-pravidla
            :type group: MorphoAnalyzerLibma.MAWordGroup
            """
            self._groups.append(group)

        def delGroup(self, group):
            """
            Smaže danou skupinu.

            :param group: Skupina, které bude smazána.
            :type group:MorphoAnalyzerLibma.MAWordGroup
            """

            self._groups.remove(group)

        def getAll(self, valFilter: Set[MorphCategory] = None, notValFilter: Set[MorphCategory] = None,
                   groupFlags: Set[Flag] = None) -> Dict[MorphCategories, Set[MorphCategory]]:
            """
            Vrácení všech možných hodnot mluvnických kategorií. Ve všech skupinách
            získaných při analýze slova.

            :param valFilter: (Volitelný) Filtr, který určuje pevně stanovené
                hodnoty, které musí mít dané pravidlo, aby se bralo v úvahu.
                Tedy není-li v daném pravidle vůbec zmíněná kategorie obsažena, tak pravidlo neprojde přes filtr.
                Příklad: Chci získat všechny rody jakých může nabývat slovo pokud je podstatným jménem.
                Nastavím filtr na: set(POS.NOUN)
                Chci získat všechny hodnoty pro slovo ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
            :type valFilter: Set[MorphCategory]
            :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
            :type notValFilter:Set[MorphCategory]
            :param groupFlags: Flagy, které musí mít daná skupina vázající se na slovo.
            :type groupFlags: Set[Flag]
            :return: Hodnoty mluvnických kategorií.
            :rtype: Dict[MorphCategories, Set[MorphCategory]]
            """
            if valFilter is None:
                valFilter = set()
            if notValFilter is None:
                notValFilter = set()
            if groupFlags is None:
                groupFlags = set()
            values = {}

            for g in self._groups:
                if len(g.flags & groupFlags) == len(groupFlags):
                    # má všechny flagy

                    for morphCat, morphCatValues in g.getAll(valFilter, notValFilter).items():
                        try:
                            values[morphCat] = values[morphCat] | morphCatValues
                        except KeyError:
                            # první vložení hodnoty dané kategorie
                            values[morphCat] = morphCatValues

            return values

        def getAllForCategory(self, morphCategory: MorphCategories, valFilter: Set[MorphCategory] = None,
                              notValFilter: Set[MorphCategory] = None, groupFlags: Set[Flag] = None) \
                -> Set[MorphCategory]:
            """
            Vrácení všech možných hodnot dané mluvnické kategorie. Ve všech skupinách
            získaných při analýze slova.

            :param morphCategory: Mluvnická kategorie.
            :type morphCategory: MorphCategories
            :param valFilter: (Volitelný) Filter, který určuje pevně stanovené
                hodnoty, které musí mít dané pravidlo, aby se bralo v úvahu.
                Tedy není-li v daném pravidle vůbec zminěná kategorie obsažena, tak pravidlo neprojde přes filtr.
                Příklad: Chci získat všechny rody jakých může nabývat slovo pokud je podstatným jménem.
                Nastavím filtr na: set(POS.NOUN)
                Chci získat všechny hodnoty pro slovo ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
            :type valFilter: Set[MorphCategory]
            :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
            :type notValFilter:Set[MorphCategory]
            :param groupFlags: Flagy, které musí mít daná skupina vázající se na slovo.
            :type groupFlags: Set[Flag]
            :return: Hodnoty dané mluvnické kategorie.
            :rtype: Set[MorphCategory]
            """

            if valFilter is None:
                valFilter = set()
            if notValFilter is None:
                notValFilter = set()
            if groupFlags is None:
                groupFlags = set()
            values = set()

            for g in self._groups:
                if len(g.flags & groupFlags) == len(groupFlags):
                    # má všechny flagy
                    values |= g.getAllForCategory(morphCategory, valFilter, notValFilter)

            return values

        def getMorphs(self, valFilter: Set[MorphCategory] = None, notValFilter: Set[MorphCategory] = None,
                      wordFilter: Set[MorphCategory] = None, groupFlags: Set[Flag] = None) -> Set[Tuple[MARule, str]]:
            """
            Získání tvarů.

            :param valFilter: (Volitelný) Filtr, který určuje pevně stanovené
                hodnoty, které musí mít pravidlo tvaru, aby se bral v úvahu daný tvar.
                Tedy není-li v daném pravidle tvaru vůbec zminěná kategorie obsažena, tak tvar neprojde přes filtr.
                Příklad: Chci získat všechny tvary, které jsou podstatným jménem, tak
                nastavím filtr na: dict(MorphCategories.POS: set(POS.NOUN))
                Chci získat všechny tvary ve středním a ženském rodě: set(Gender.NEUTER, Gender.FEMINE)
            :type valFilter: Set[MorphCategory]
            :param notValFilter: Stejné jako valFilter s tím rozdílem, že dané hodnoty nesmí pravidlo tvaru obsahovat.
            :type notValFilter:Set[MorphCategory]
            :param wordFilter: Podmínky na původní slovo. Jelikož analýza nám může říci několik variant, tak tímto filtrem můžeme
                spřesnit odhad.
                Chceme-li získat všechny tvary, které se váží na případy, kdy se předpokládá, že původní slovo mělo
                danou morfologickou kategorii, tak použijeme tento filtr.
                    Příklad: Pokud je vložen 1. pád. Budou brány v úvahu jen tvary, které patří ke skupině tvarů vázajících se na případ
                    že původní slovo je v 1. pádu.
            :type wordFilter: Set[MorphCategory]
            :param groupFlags: Flagy, které musí mít daná skupina vázající se na slovo.
            :type groupFlags: Set[Flag]
            :return: Množinu dvojic (pravidlo, tvar).
            :rtype: Set[Tuple[MARule,str]]
            """
            if valFilter is None:
                valFilter = set()
            if notValFilter is None:
                notValFilter = set()
            if wordFilter is None:
                wordFilter = set()
            if groupFlags is None:
                groupFlags = set()
            morphs = set()

            for g in self._groups:

                if len(g.flags & groupFlags) == len(groupFlags):
                    # má všechny flagy
                    if len(g.getAll(wordFilter)):
                        morphs |= g.getMorphs(valFilter, notValFilter)

            return morphs

        @property
        def groups(self):
            """
            Skupiny z morfologické analýzy.

            :rtype: List(MAWordGroup)
            """

            return self._groups

        @property
        def derivations(self) -> List[str]:
            """
            Odvozená slova.
            """
            res = []
            for g in self._groups:
                res.extend(g.getDerivations())
            return res

        def __str__(self):
            s = ""
            for g in self._groups:
                s += str(g)
            s += "----------"
            return s

    def prepareNameDependentAnalysis(self, names):
        """
        Přípraví analýzou závislou na jménu.

        :param names: Předpokládáme, že jsou jména seřazena vzestupně.
        :type names: List[Name]

        """

        """
        Přiřadí k aktuálnímu slovníku, vztaženému ke jménu, druh pro každou potenciální zkratku předložky, který říká,
        že zkratka může právě být zkratkou předložky.

        Pracuje na základě hledání korespondencí.
        Hledá korespondence typu: Bernstadt auf dem Eigen <->  Bernstadt a. d. Eigen
        Pokud existují takováto jména, pak při na jménu závislé analýze přiřadí příslušné flagy ke zkratkám.
        
        """

        # Tvoříme vlastně rozklad na třídy ekvivalence, dle relace ekvivalence definované výše uvedenou korespondencí.
        self._prepAbberEqClasses = {}
        for n in names:
            if len(n) > 2:
                try:
                    self._prepAbberEqClasses[EQRelationForPrepAndItsAbbre(n)].add(n)
                except KeyError:
                    self._prepAbberEqClasses[EQRelationForPrepAndItsAbbre(n)] = {n}

        # odfiltrujeme všechny třídy s méně jak 2 položkami
        self._prepAbberEqClasses = {eqR: names for eqR, names in self._prepAbberEqClasses.items() if len(names) > 1}

    def __init__(self, pathToMa, words, hint=None):
        """
        Provede vytvoření objektu Morfologického analyzátoru.
        Spustí nad všemy slovy z words morfologický analyzátor s parametry:
            -F vrací všechny možné tvary.
            -m Na výstup se vypíše flektivní analýza zadaného slova.
            -n Přidá poznámku.
            -D Odvozená slova. (jsou automaticky přidána)
        Výsledek si poté načte a bude sloužit jako databáze, která bude použita pro získávání informací
        o slovech.

        :param pathToMa: Cesta/ příkaz pro spuštění morfologického analyzátoru.
        :type pathToMa: str
        :param words: Slova, která budou předložena analyzátoru a vysledek budou sloužit jako databáze
            pro tuto obálku. Objekt bude tedy znát nanejvýše tato slova.
        :type words: set(str)
        :param hint: Volitelný parametr, který dává nápovědu k hodnotě morfologické kategorie slova.
            Například pokud víme, že slovo je v prním pádu, tak použijeme tento parametr k odfiltrování dalších možností.
            Pokud je předán set, platí nápověda pro všechny slova stejná. Pokud je předán Dict, tak pro každé slovo je jiná (klíč udává slovo pro nějž nápověda platí).
            Pozor pokud se daná morfologická kategorie vůbec v analýze slova nevyskytuj, pak je nápověda ignorována.
        :type hint: :Set[MorphCategory] | Dict[MorphCategory]
        :raise MorphoAnalyzerException: Chyba analyzátoru.
        """
        self._hint = hint
        # vytvoříme novou prázdnou databázi slov
        self._wordDatabase = {}

        self._pathToMa = pathToMa

        # získání informací o slovech
        words = list(words)
        self.__commWithMA(words)

        # přidejme slova odvozená
        derivated = set()
        for w in self._wordDatabase.values():
            for g in w.groups:
                for d, _ in g.getDerivations():
                    if d not in self._wordDatabase:
                        derivated.add(d)
        derivated = list(derivated)

        self.__commWithMA(derivated)
        words.extend(derivated)

        # Rozklad na třídy ekvivalence.
        # Ve formě dict.
        # Ekvivalence je typu: Bernstadt auf dem Eigen <->  Bernstadt a. d. Eigen
        # Tedy je ekvivalentní ke svým zkraceným formám.
        self._prepAbberEqClasses = {}

        for w in words:
            if len(w) >= 2 and w.isupper() or len(w) == 2 and w[-1] == ".":
                # Určíme všechna slova obsahující pouze velká písmena, která jsou dlouhá alespoň dva znaky jako zkratku.
                # a
                # Všechna jednopísmenná slova zakončená tečku označíme za možnou zkratku.
                g = self.MAWordGroup(w)
                g.lemma = w

                g.addTagRule(POS.ABBREVIATION.lntrf)
                g.addMorph(POS.ABBREVIATION.lntrf, w)
                try:
                    wordAnalyze = self._wordDatabase[w]
                    if POS.ABBREVIATION not in wordAnalyze.getAllForCategory(MorphCategories.POS):
                        # Zatím není možnou zkratkou, tak přidáme.
                        wordAnalyze.addGroup(g)
                except KeyError:
                    # slovo zatím není v databázi vůbec
                    self._wordDatabase[w] = self.MAWord()
                    self._wordDatabase[w].addGroup(g)

        # přidáme ke slovům von, da a de
        # analýzu, že se jedná o předložky za nimiž se slova ohýbají
        for prep in ["dalla", "de", "der", "da", "del", "di", "dos", "el", "la", "le", "van", "von", "und", "ben",
                     "bin", "y", "zu"]:
            for w in [prep, prep.capitalize()]:  # generujeme variantu s velkým a malým písmenem na začátku
                g = self.MAWordGroup(w)
                g.lemma = w

                g.addTagRule(POS.PREPOSITION_M.lntrf)
                g.addMorph(POS.PREPOSITION_M.lntrf, w)
                try:
                    self._wordDatabase[w].addGroup(g)
                except KeyError:
                    # slovo zatím není v databázi
                    self._wordDatabase[w] = self.MAWord()
                    self._wordDatabase[w].addGroup(g)

        # pro nás je a pouze spojka
        try:
            ma = self._wordDatabase["a"]

            delGroups = [group for group in ma.groups if group.rules[0][MorphCategories.POS] != POS.CONJUNCTION]

            for g in delGroups:
                ma.delGroup(g)

        except KeyError:
            pass

        # vynecháváme, protože v našem případě nemůžou být písmena podstatným jménem
        for c in string.ascii_letters:
            try:
                ma = self._wordDatabase[c]

                for group in ma.groups:
                    if Note.CHARACTER_AS_NOUN in group.rules[0][MorphCategories.NOTE]:
                        ma.delGroup(group)

            except KeyError:
                pass

    def __commWithMA(self, words):
        """
        Pošle ma slova, která mají být analyzována.

        :param words: Slova pro analýzu
        :type words:List[str]
        :raise MorphoAnalyzerException: Chyba analyzátoru.
        """

        p = Popen([self._pathToMa, "-F", "-m", "-n", "-D"], stdin=PIPE, stdout=PIPE, stderr=None)

        output, _ = p.communicate(str.encode(("\n".join(words)) + "\n"))  # vrací stdout a stderr

        # zkontrolujeme návratový kód
        if p.returncode != 0:
            # selhání analyzátoru
            raise MorphoAnalyzerException(ErrorMessenger.CODE_MA_FAILURE)

        retWords = self._parseMaOutput(output.decode())

        if retWords != len(words):

            # nemáme všechna slova
            # zřejmě byl pro komunikaci výstup příliš velký pokusíme se poslat méně slov
            if len(words) == 1:
                # Níž nelze. Vynecháme toto slovo. Není pravděpodobné, že by jedno slovo mělo tak příliš velký výstup
                # zřejmě se spíše jedná o nevhodné slovo pro ma. Jako je například slovo . (tečka).
                return

            origCnt = len(words)
            words = words[retWords:]  # zbavíme se již zpracovaných

            partSize = math.ceil(len(words) / 2)
            logging.info("\tPři komunikaci s ma došlo ke ztrátě slov (odesláno: " + str(origCnt) + ", přijato: " + str(
                retWords) + "). Pokusím se o komunikaci znovu s menším počtem slov: " +
                         str(origCnt) + " -> " + str(partSize) + ".")
            for offset in range(0, len(words), partSize):
                self.__commWithMA(words[offset:offset + partSize])

    def _parseMaOutput(self, output):
        """
        Provede analýzu výstupu z ma a uloží získané informace do databáze.

        :param output: Výstup z analyzátoru.
        :type output: str
        :return: Počet získaných slov. (i nezpracovaných ma>--not found)
        :rtype: int
        :raise MorphoAnalyzerException: Pokud se nepodaří analyzovat vstup.
        """

        actWordGroup = None  # obsahuje data k aktuálně parsované skupině
        cntUnWords = 0
        wordsInDBAtStart = len(self._wordDatabase)
        for lineNumber, line in enumerate(output.splitlines()):
            try:
                if line == "ma>--not found":
                    # máme další slovo, ale nezpracované
                    cntUnWords += 1
                    continue

                # rozdělení řádku
                parts = line.strip().split()
                if parts[0][-3:] == "<s>":
                    # začínáme číst novou skupinu slova
                    # <s> vstupní slovo (vzor 1)

                    # byla předešlá skupina k něčemu dobrá?
                    if actWordGroup is not None and len(actWordGroup.rules) == 0:
                        # ne nebyla, tak ji odstraníme
                        self._wordDatabase[actWordGroup.word].delGroup(actWordGroup)

                    # vytvoříme skupinu
                    actWordGroup = self.MAWordGroup(parts[1])

                    try:
                        # vložíme skupinu do analýzy slova
                        self._wordDatabase[parts[1]].addGroup(actWordGroup)
                    except KeyError:
                        # nové slovo
                        # vytvoříme objekt pro uložení morfologické analýzy slova
                        self._wordDatabase[parts[1]] = self.MAWord()
                        # a znovu vložíme
                        self._wordDatabase[parts[1]].addGroup(actWordGroup)

                elif parts[0][:3] == "<c>":
                    # značko pravidlo, které sedí pro dané slovo

                    if isinstance(self._hint, dict) or isinstance(self._hint, set):
                        # aplikujeme nápovědu
                        convRule = self.MAWordGroup.convTagRule(parts[0][3:])

                        hint = self._hint[actWordGroup.word] if isinstance(self._hint, dict) else self._hint
                        if all(f.category() not in convRule or convRule[f.category()] == f for f in hint):
                            actWordGroup.addTagRuleConv(convRule)
                    else:
                        actWordGroup.addTagRule(parts[0][3:])
                elif parts[0][:3] == "<l>":
                    # lemma slova
                    if parts[0][3:][0].islower():
                        # malé první písmeno u lematu
                        # nastavujeme jako obecné slovo
                        # pokud se dále ukáže, že má tato skupina poznámku, pak bude
                        # tento flag odstraněn samotným objektem třídy MAWordGroup.
                        actWordGroup.addFlag(Flag.GENERAL_WORD)

                elif parts[0][:3] == "<f>":
                    # Přidání tvaru slova
                    # pouze pokud je relevantní k znočko pravidlům, které sedí na dané slovo.
                    # Tento požadavek si můžeme dovolit, jelikoř v tuto dobu by měly být zpracovány
                    # všechny <c> řádky.

                    actWordGroup.addMorph((parts[0][3:])[1:-1], parts[1], True)
                elif parts[0][:3] == "<d>":
                    # přidání odvozeného tvaru slova
                    t = None
                    if len(parts[0]) > 3:
                        t = parts[0][4:-1]

                    actWordGroup.addDerivation(parts[1], t)

            except IndexError:
                raise MorphoAnalyzerException(ErrorMessenger.CODE_MA_CAN_NOT_READ_OUTPUT,
                                              ErrorMessenger.getMessage(ErrorMessenger.CODE_MA_CAN_NOT_READ_OUTPUT)
                                              .format(lineNumber) + "\n\t" + line)

        # byla předešlá skupina k něčemu dobrá?
        if actWordGroup is not None and len(actWordGroup.rules) == 0:
            # nebyla
            self._wordDatabase[actWordGroup.word].delGroup(actWordGroup)

        return cntUnWords + len(self._wordDatabase) - wordsInDBAtStart

    def isNameDependant(self, word: str, name) -> bool:
        """
        Zjistí zdali daná kombinace slova a jména má na jméně závislou analýzu.

        :param word: slovo pro analýzu
        :type word: str
        :param name: Celé jméno v němž je předané slovo obsaženo.
        :type name: Name
        :return: True -> Slovo má na jméně závislou analýzu.
                False -> nemá
        :rtype: bool
        """

        return EQRelationForPrepAndItsAbbre(name) in self._prepAbberEqClasses and \
            POS.ABBREVIATION in self._wordDatabase[word].getAllForCategory(MorphCategories.POS)

    def analyze(self, word, name=None, wordPos: Optional[int] = None):
        """
        Získání kompletních znalostí o slově. Slovo by mělo být
        jedním ze slov předaných v konstruktoru.

        :param word: slovo pro analýzu
        :type word: str
        :param name: Pokud je tento parametr neprázdný pak provede analýzu slova závislou na předaném jménu.
        :type name: Optional[Name]
        :param wordPos: Pozice slova ve jméně.
        :type wordPos: Optional[int]
        :return: Analýza slova. None pokud není slovo v databázi.
        :rtype: MAWord
        :raise ValueError: Může někdy hodit tuto vyjímku pokud není dané slovo v poskytnutém jméně, je-li ovšem jméno
            vůbec poskytnuto.
        """

        try:
            wordAnalyze = self._wordDatabase[word]
        except KeyError:
            return None

        if name is not None:
            eqR = EQRelationForPrepAndItsAbbre(name)

            if eqR in self._prepAbberEqClasses and \
                    POS.ABBREVIATION in self._wordDatabase[word].getAllForCategory(MorphCategories.POS):
                # Máme na jménu závislou analýzu pro toto slovo.

                # Budeme zkoušet zdali neexistuje prvek v ekv. třídě,
                # který má slovo na stejné pozici a je předložkou.

                if wordPos is not None and \
                        any((POS.PREPOSITION in self._wordDatabase[str(n[wordPos])].getAllForCategory(MorphCategories.POS))
                            for n in self._prepAbberEqClasses[eqR]):
                    # Vytvoříme se prázdnou novou analýzu slova, protože jsme si na základě získaného kontextu
                    # jistější o tom, že je to zkratka předložky a jiné možnosti tedy zamítneme.
                    wordAnalyze = self.MAWord()
                else:
                    # zkopírujeme co o slovu již víme
                    wordAnalyze = copy(wordAnalyze)

                # Přidáme možnost ke zkratkám, že se může jednat o zkratku předložky.
                g = self.MAWordGroup(word)
                g.lemma = word

                g.addTagRule(POS.PREPOSITION_ABBREVIATION.lntrf)
                g.addMorph(POS.PREPOSITION_ABBREVIATION.lntrf, word)

                wordAnalyze.addGroup(g)

        return wordAnalyze
