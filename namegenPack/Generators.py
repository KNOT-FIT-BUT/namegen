"""
Created on 04. 08. 2019
Modul obsahující generátory vytvářející nová jména ze starých.

:author:     Martin Dočekal
:contact:    xdocek09@stud.fit.vubtr.cz
"""

from abc import ABC, abstractmethod
from copy import copy
from typing import List, Tuple, Set, Union, AbstractSet, Optional

from namegenPack.Grammar import Grammar
from namegenPack.Name import Name, NameMorph
from namegenPack.Word import WordTypeMark, Word
from namegenPack.morpho.MorphCategories import MorphCategory, MorphCategories, Note
from namegenPack.morpho.MorphoAnalyzer import MorphoAnalyze, MorphoAnalyzerLibma


class Generator(ABC):
    """
    Generátor je funktor schopný vegenerovat z jednoho jména jiné/á jméno/a.
    """

    @abstractmethod
    def __call__(self, nameMorphs: List[NameMorph]) -> List[Tuple[Name, List[NameMorph]]]:
        """
        Volání generátoru.

        :param nameMorphs: Tvary slova.
            (NameMorph obsahuje svoje původní slovo, tak není třeba dodávat.)
        :type nameMorphs: List[NameMorph]
        :return: Dvojice nové vygenerované jméno s nově vygenerovanými tvary.
        :rtype: List[Tuple[Name, List[NameMorph]]]:
        """
        pass


class GenerateNope(Generator):
    """
    Tento generátor nikdy nic negeneruje.
    """

    def __call__(self, nameMorphs: List[NameMorph]) -> List[Tuple[Name, List[NameMorph]]]:
        """
        Volání generátoru.

        :param nameMorphs: Tvary slova.
            (NameMorph obsahuje svoje původní slovo, tak není třeba dodávat.)
        :type nameMorphs: List[NameMorph]
        :return: Dvojice nové vygenerované jméno s nově vygenerovanými tvary.
        :rtype: List[Tuple[Name, List[NameMorph]]]:
        """

        return None


class MultiGenerator(Generator):
    """
    Generátor složený z více generátorů.
    """

    def __init__(self, generators: List[Generator]):
        """
        Inicializace generátoru.

        :param generators: Seznam generátorů, které budou použity.
        :type generators: List[Generator]
        """

        self.generators = generators

    def __call__(self, nameMorphs: List[NameMorph]) -> List[Tuple[Name, List[NameMorph]]]:
        """
        Volání generátoru.

        :param nameMorphs: Tvary slova.
            (NameMorph obsahuje svoje původní slovo, tak není třeba dodávat.)
        :type nameMorphs: List[NameMorph]
        :return: Dvojice nové vygenerované jméno s nově vygenerovanými tvary.
        :rtype: List[Tuple[Name, List[NameMorph]]]:
        """

        ret = []
        for g in self.generators:
            ret.extend(g(nameMorphs))

        return ret


class GenerateDerivatedForms(Generator):
    """
    Generování odvozených tvarů.

    Příklad:
        z:          Masaryk
        vygeneruje: Masarykův, Masarykovi, Masaryková
    """

    def __init__(self, allowedDerivTypes: Optional[AbstractSet[Tuple[str, Optional[str]]]] = None, lemma_first_letter_capital: bool = False):
        """
        Inicializace generátoru.

        :param allowedDerivTypes: Povolené druhy odvozených tvarů. Pokud None tak povolíme všechny.
            množina dvojic (typ relace, poznamka)
        :type allowedDerivTypes: Optional[AbstractSet[Tuple[str, Optional[str]]]]
        :param lemma_first_letter_capital: Pokud je pravda, tak se bude předpokládat, že lemma musi mít první písmeno velké.
        :type lemma_first_letter_capital: bool
        """

        self.allowedDerivTypes = None
        if allowedDerivTypes is not None:
            self.allowedDerivTypes = {relation: note for relation, note in allowedDerivTypes}

        self.lemma_first_letter_capital = lemma_first_letter_capital

    def filterDerivations(self, derivations: List[Tuple[str, Tuple[str, Optional[str]]]]) -> List[Tuple[str, Optional[str]]]:
        """
        Vyfiltruje odvozené tvary podle povolených typů.
        Poznámka je volitelná, ale pokud není None tak se musí shodovat.

        :param derivations: Seznam odvozených tvarů.
        :type derivations: List[Tuple[str, Tuple[str, Optional[str]]]]
        :return: Vyfiltrované tvary.
        """
        if self.allowedDerivTypes is None:
            return derivations

        filtered = []
        for d in derivations:
            if d[1][0] in self.allowedDerivTypes:
                note = self.allowedDerivTypes[d[1][0]]
                if note is None or note == d[1][1]:
                    filtered.append(d)

        return filtered

    def __call__(self, nameMorphs: List[NameMorph]) -> List[Tuple[Name, List[NameMorph]]]:
        """
        Dojde ke generování jmen na základě odvozených tvarů

        :param nameMorphs: Tvary jednoho slova.
        :type nameMorphs: List[NameMorph]
        :return: Dvojice nové vygenerované jméno s nově vygenerovanými tvary.
        :rtype: List[Tuple[Name, List[NameMorph]]]:
        """

        generatedNames = []
        name: Name = nameMorphs[0].forName

        if name.type != Name.Type.MainType.PERSON:
            # jen jména osob
            return []

        countableWords = {
            WordTypeMark.GIVEN_NAME, WordTypeMark.SURNAME, WordTypeMark.LOCATION,
            WordTypeMark.EVENT, WordTypeMark.UNIQ_NAME, WordTypeMark.FEMALE_PATRONYM, WordTypeMark.MALE_PATRONYM,
            WordTypeMark.ALIAS, WordTypeMark.HOUSE, WordTypeMark.UNKNOWN
        }

        derivate_from = None

        for i, (t, _) in enumerate(nameMorphs[0].wordsTypes):
            if t in countableWords:
                if derivate_from is not None:
                    # jen jednoslovná jména (zastinujeme rimske cislice, tituly, atd.)
                    return []
                derivate_from = i

        if derivate_from is None:
            # nic k derivaci
            return []

        if name.language is None:
            return []

        a: MorphoAnalyzerLibma.MAWord = name.language.ma.analyze(str(name.words[derivate_from]))
        if a is None:
            return []

        derivatedWords = []
        for g in a.groups:
            if self.lemma_first_letter_capital and not g.lemma[0].isupper():
                # lemma musi mit prvni pismeno velke
                continue
            deriv = self.filterDerivations(g.getDerivations())
            derivatedWords.extend(deriv)
        for w, d_type in derivatedWords:
            newName = name.copy()
            newName.words[derivate_from] = Word(w, newName, derivate_from)

            newName.generated = True
            note = d_type[0]
            if d_type[1] is not None:
                note += "#" + d_type[1]
            newName.additionalInfo.append(note)   # přidáme informaci o tom, že se jedná o odvozený tvar a jaký

            tokens = newName.language.lex.getTokens(newName)

            try:
                _, aTokens = newName.grammar.analyse(tokens)
            except (Grammar.NotInLanguage, Grammar.TimeoutException):
                continue

            for derivATokens in aTokens:
                try:
                    morphs = newName.genMorphs(derivATokens)
                    for morph in morphs:
                        for i, wT in enumerate(morph.wordsTypes):
                            morph.wordsTypes[i] = (WordTypeMark.UNKNOWN, wT[1])

                    generatedNames.append((newName, morphs))

                except Word.WordException:
                    continue
        return generatedNames


class GenerateAbbreFormOfPrep(Generator):
    """
    Generování formy v podobě zkratky vytvořené z předložek (uprostřed slova) v daném názvu/jménu.

    Příklad:
        z:          Nové Město na Moravě
        vygeneruje: Nové Město n. Moravě
    """

    def __init__(self, allowedNameTypes: Set[Union[Name.Type, Name.Type.PersonGender]]):
        """
        Inicializace generátoru.

        :param allowedNameTypes: Povolené druhy jména. Ostatní nerozgenerovává.
        :type allowedNameTypes: Set[Union[Name.Type, Name.PersonGender]]
        """

        self.allowedNameTypes = allowedNameTypes

    def __call__(self, nameMorphs: List[NameMorph]) -> List[Tuple[Name, List[NameMorph]]]:
        """
        Dojde ke generování jmen s předložkami ve zkráceném tvaru.

        :param nameMorphs: Tvary jednoho slova.
        :type nameMorphs: List[NameMorph]
        :return: Dvojice nové vygenerované jméno s nově vygenerovanými tvary.
        :rtype: List[Tuple[Name, List[NameMorph]]]:
        """

        # jméno musí mít více jak 2 slova, protože hledáme jen uprostred
        # kontrola typu
        # jedná se o předložku delší než jeden znak a hledáme jen uprostřed jména
        if len(nameMorphs[0].wordsMorphs) > 2 and \
                any(nameMorphs[0].forName.type == alloT for alloT in self.allowedNameTypes) and \
                any(nameMorphs[0].wordsTypes[i][0] == WordTypeMark.PREPOSITION and  # jedná se o předložku
                    len(next(iter(nameMorphs[0].wordsMorphs[i]))[0]) > 1  # delší než jeden znak
                    for i in range(1, len(nameMorphs[0].wordsMorphs) - 1)):  # hledáme jen uprostřed jména

            # ve jméně se vyskytuje alespoň jedna předložka pro zkrácení

            newMorphs = []

            # Budeme sestavovat nová slova (nové jsou jen předložky) pro jméno.

            newName = copy(nameMorphs[0].forName)

            newName.generated = True

            newNameNotFilled = True  # Flag, který určuje, že se má získat nová podoba slov pro nové jméno
            newName.words = []

            for nameM in nameMorphs:
                newWordsM = []
                newWordsTypes = []
                for i, (wordMorphs, wordMark) in enumerate(zip(nameM.wordsMorphs, nameM.wordsTypes)):

                    if i != 0 and i != len(nameM.wordsMorphs) - 1 and wordMark[0] == WordTypeMark.PREPOSITION and \
                            len(next(iter(wordMorphs))[0]) > 1:
                        # máme předložku pro zkrácení
                        # vyrobíme zkratky (nad -> n.)
                        newWordMorphs = {(wordM[0] + ".", wordRule) for wordM, wordRule in wordMorphs}
                        newWordsM.append(newWordMorphs)
                        newWordsTypes.append((WordTypeMark.PREPOSITION_ABBREVIATION, wordMark[1]))

                        if newNameNotFilled:
                            # Pro nové jméno přidáme nově zkrácenou předložku.
                            # Z množiny možných tvarů jednoho slova vybereme jednoduše jedno náhodně.
                            # Nic jiného nám moc nezbývá a u předložek by to mělo být stejně spíše jedno.
                            newName.words.append(next(iter(newWordMorphs))[0])
                    else:
                        # nemáme předložku prostě dáme co máme nezměněné
                        newWordsM.append(copy(wordMorphs))
                        newWordsTypes.append(wordMark)

                        if newNameNotFilled:
                            # Pro nové jméno přidáme slovo v původním tvaru.
                            newName.words.append(nameM.forName.words[i])

                # Máme všechna data pro nové jméno po prvním kole.
                newNameNotFilled = False

                newMorphs.append(NameMorph(newName, newWordsM, newWordsTypes))

            return [(newName, newMorphs)]

        return []
