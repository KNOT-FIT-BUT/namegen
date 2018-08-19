#!/usr/bin/env python3
# encoding: utf-8
"""
namegen -- Generátor tvarů jmen.

namegen je program pro generování tvarů jmen osob a lokací.

:author:     Martin Dočekal
:contact:    xdocek09@stud.fit.vubtr.cz
"""

import sys
import os
from argparse import ArgumentParser
import traceback
from namegenPack import Errors
import logging
import namegenPack.Grammar
import namegenPack.morpho.MorphoAnalyzer
import namegenPack.morpho.MorphCategories
import configparser

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

    sectionDataFiles="DATA_FILES"
    sectionMorphoAnalyzer="MA"
    
    
    
    
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
            raise ConfigManagerInvalidException(Errors.ErrorMessenger.CODE_INVALID_CONFIG, "Nevalidní konfigurační soubor: "+str(e))
                                       
        
        return self.__transformVals()
        
        
    def __transformVals(self):
        """
        Převede hodnoty a validuje je.
        
        :returns: dict -- ve formátu jméno sekce jako klíč a k němu dict s hodnotami.
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """
        result={}

        result[self.sectionDataFiles]=self.__transformDataFiles()
        result[self.sectionMorphoAnalyzer]=self.__transformMorphoAnalyzer()
        
        return result
    
    def __transformMorphoAnalyzer(self):
        """
        Převede hodnoty pro MA a validuje je.
        
        :returns: dict -- ve formátu jméno prametru jako klíč a k němu hodnota parametru
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """

        result={
            "PATH_TO":self.configParser[self.sectionMorphoAnalyzer]["PATH_TO"]
            }

        return result
    
    def __transformDataFiles(self):
        """
        Převede hodnoty pro DATA_FILES a validuje je.
        
        :returns: dict -- ve formátu jméno prametru jako klíč a k němu hodnota parametru
        :raise ConfigManagerInvalidException: Pokud je konfigurační soubor nevalidní.
        """

        result={
            "TAGGER":None,
            "DICTIONARY":None,
            "GRAMMAR_MALE":None,
            "GRAMMAR_FEMALE":None,
            "GRAMMAR_LOCATIONS":None
            }
        self.__loadPathArguments(self.configParser[self.sectionDataFiles], result)

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
                if parConf[k][0]!="/":
                    result[k]=os.path.dirname(os.path.realpath(__file__))+"/"+parConf[k]
                else:
                    result[k]=parConf[k]
            else:
                raise ConfigManagerInvalidException(Errors.ErrorMessenger.CODE_INVALID_CONFIG, "Nevalidní konfigurační soubor. Chybí "+self.sectionDataFiles+" -> "+k)


class ArgumentParserError(Exception): pass
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
        
        parser.add_argument("-o", "--output", help="Výstupní soubor.", type=str, required=True)
        parser.add_argument("-ew", "--error-words", help="Cesta k souboru, kde budou uloženy slova, pro která se nepovedlo získat informace (tvary, slovní druh...).", type=str)
        parser.add_argument('input', nargs=1, help='Vstupní soubor se jmény.')

        try:
            parsed=parser.parse_args()
            
        except ArgumentParserError as e:
            parser.print_help()
            print("\n"+str(e), file=sys.stderr)
            Errors.ErrorMessenger.echoError(Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_INVALID_ARGUMENTS), Errors.ErrorMessenger.CODE_INVALID_ARGUMENTS)

        return parsed
 
def main():
    """
    Vstupní bod programu.
    """
    try:
        
        logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
        #zpracování argumentů
        args=ArgumentsManager.parseArgs()
        
        #načtení konfigurace
        configManager=ConfigManager()
        configAll=configManager.read(os.path.dirname(os.path.realpath(__file__))+'/namegen_config.ini')
        
        
        logging.info("načtení gramatik")
        #načtení gramatik
        try:
            grammarMale=namegenPack.Grammar.Grammar(configAll[configManager.sectionDataFiles]["GRAMMAR_MALE"])
        except Errors.ExceptionMessageCode as e:
            raise Errors.ExceptionMessageCode(e.code, configAll[configManager.sectionDataFiles]["GRAMMAR_MALE"]+": "+e.message)
        
        try:
            grammarFemale=namegenPack.Grammar.Grammar(configAll[configManager.sectionDataFiles]["GRAMMAR_FEMALE"])
        except Errors.ExceptionMessageCode as e:
            raise Errors.ExceptionMessageCode(e.code, configAll[configManager.sectionDataFiles]["GRAMMAR_FEMALE"]+": "+e.message)
        
        try:
            grammarLocations=namegenPack.Grammar.Grammar(configAll[configManager.sectionDataFiles]["GRAMMAR_LOCATIONS"])
        except Errors.ExceptionMessageCode as e:
            raise Errors.ExceptionMessageCode(e.code, configAll[configManager.sectionDataFiles]["GRAMMAR_LOCATIONS"]+": "+e.message)
        logging.info("\thotovo")
        logging.info("čtení jmen")
        #načtení jmen pro zpracování
        namesR=NameReader(args.input[0])
        logging.info("\thotovo")
        logging.info("analýza slov")
        #přiřazení morfologického analyzátoru
        Word.setMorphoAnalyzer(
            namegenPack.morpho.MorphoAnalyzer.MorphoAnalyzerLibma(
                configAll[configManager.sectionMorphoAnalyzer]["PATH_TO"], 
                namesR.allWords(True)))
        logging.info("\thotovo")
        logging.info("\tgenerování tvarů")
        #čítače chyb
        errorsOthersCnt=0   
        errorsGrammerCnt=0  #není v gramatice
        errorsWordInfoCnt=0   #nemůže vygenrovat tvary, zjistit POS...

        errorWordsShouldSave=True if args.error_words is not None else False
        errorWords=set()    #slova ke, kterým nemůže vygenerovat tvary, zjistit POS... Jedná se o dvojice ( druhu slova ve jméně, dané slovo)
         
        cnt=0   #projito slov
        
        #nastaveni logování
        

        with open(args.output, "w") as outF:
            
            for name in namesR:
                try:
                    
                    #Vybrání a zpracování gramatiky na základě druhu jména.
                    #získáme aplikovatelná pravidla, ale hlavně analyzované tokeny, které mají v sobě informaci,
                    #zda-li se má dané slovo ohýbat, či nikoliv a další
                    
                    #rules a aTokens může obsahovat více než jednu možnou derivaci
                    if name.type==Name.Type.LOCATION:
                        r, aTokens=grammarLocations.analyse(namegenPack.Grammar.Lex.getTokens(name))
                    elif name.type==Name.Type.MALE:
                        r, aTokens=grammarMale.analyse(namegenPack.Grammar.Lex.getTokens(name))
                    else:
                        r, aTokens=grammarFemale.analyse(namegenPack.Grammar.Lex.getTokens(name))

                    completedMorphs=set()    #pro odstranění dualit používáme set
                    for aT in aTokens:
                        morphs=name.genMorphs(aT)
                        completedMorphs.add(str(name)+"\t"+str(name.type)+"\t"+("|".join(morphs)))
                    
                    #vytiskneme
                    for m in completedMorphs:
                        print(m, file=outF)
                        
                except (Word.WordException) as e:
                    print(str(name)+"\t"+e.message, file=sys.stderr)
                    errorsWordInfoCnt+=1
    
                    if errorWordsShouldSave:
                        try:
                            for m, w in zip(name.markWords(), name.words):
                                if w==e.word:
                                    errorWords.add((m, e.word))
                        except:
                            #nelze získat informaci o druhu slova ve jméně
                            errorWords.add(("", e.word))
                            pass
                        
                except namegenPack.Grammar.Grammar.NotInLanguage as e:
                    errorsGrammerCnt+=1
                    print(Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_NAME_IS_NOT_IN_LANGUAGE_GENERATED_WITH_GRAMMAR)+\
                              "\t"+str(name)+"\t"+str(name.type)+"\t"+e.message, file=sys.stderr)

                except Errors.ExceptionMessageCode as e:
                    #chyba při zpracování slova
                    errorsOthersCnt+=1
                    print(str(name)+"\t"+e.message, file=sys.stderr)
                    
                cnt+=1
                if cnt%100==0:
                    logging.info("Projito slov: "+str(cnt))
                
        logging.info("\thotovo")
        print("-------------------------")
        print("Celkem jmen: "+ str(namesR.errorCnt+len(namesR.names)))
        print("\tNenačtených jmen: "+ str(namesR.errorCnt))
        print("\tNačtených jmen/názvů celkem: ", len(namesR.names))
        print("\t\tNepokryto gramatikou: ", errorsGrammerCnt)
        print("\t\tNepodařilo se získat informace o slově (tvary, slovní druh...): ", errorsWordInfoCnt)
        
        
        if errorWordsShouldSave:
            #save words with errors into a file
            with open(args.error_words, "w") as errWFile:
                for m, w in errorWords:#označení typu slova ve jméně(jméno, příjmení), společně se jménem
                    try:
                        #TODO: +"\t"+ w.info. Morphodita.Morphodita.transInfoToLNTRF(w.info), file=errWFile)
                        print(str(w)+"\t"+"j"+str(m))
                    except Word.WordException:
                        #no info
                        print(str(w), file=errWFile)
        
  

    except Errors.ExceptionMessageCode as e:
        Errors.ErrorMessenger.echoError(e.message, e.code)
    except IOError as e:
        Errors.ErrorMessenger.echoError(Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_COULDNT_WORK_WITH_FILE)+"\n"+str(e), 
                                 Errors.ErrorMessenger.CODE_COULDNT_WORK_WITH_FILE)

    except Exception as e: 
        print("--------------------", file=sys.stderr)
        print("Detail chyby:\n", file=sys.stderr)
        traceback.print_tb(e.__traceback__)
        
        print("--------------------", file=sys.stderr)
        print("Text: ", end='', file=sys.stderr)
        print(e, file=sys.stderr)
        print("--------------------", file=sys.stderr)
        Errors.ErrorMessenger.echoError(Errors.ErrorMessenger.getMessage(Errors.ErrorMessenger.CODE_UNKNOWN_ERROR), Errors.ErrorMessenger.CODE_UNKNOWN_ERROR)

    

if __name__ == "__main__":
    main()
