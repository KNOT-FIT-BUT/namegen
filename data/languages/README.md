# Složka languages
Tato složka obsahuje jednotlivé podporované jazyky.

Složka s daným jazykem je pojmenována dle značky jazyka, která je použita na vstupu namegenu (např. čeština cs).

Samotné načítání jazyků se řídí nastavením v souboru namegen_config.ini v sekce DATA_FILES.

## Jazyky
Každý adresář jazyka musí obsahovat:

   * podadresář grammars s gramatikami
   * soubor titles.txt s tituly
   

## Tituly

Soubor s tituly obsahuje výčet slov (záleží na velikosti písmen), které mají být brány jako titul. Jednotlivé tituly jsou odděleny alespoň jedním bílým znakem (dělí python .split). Je možné přidávat řádkové komentáře pomocí #. Tituly jako Ing.arch. uvádějte bez mezery. Namegen automaticky, jeli třeba, uvažuje i variantu s mezerou.

Příklad obsahu:

	#akademické
	Bc. BcA. Ing.arch. Mgr. MgA. MUDr. MDDR. MVDr. JUDr. RNDr. PhDr.
	
## Generování ekvivalentních slov
Generování ekvivalentních slov si uvedeme na příkladu. Mějme tedy jméno:

    Sv. Petr
    
Dejme tomu, že chceme na výstupu získat i:

    Svatý Petr
    Sv Petr
    sv. Petr
    St Petr
    
K tomu slouží právě soubor (nastavení názvu souboru je v konfiguraci pod EQ_GEN=eq_gen.py)
s definovanými slovy, které se mají považovat za ekvivalentní, pro náš příklad, by mohl vypadat následovně:

    {
        "P:::M": [
            {"Sv.", "Sv", "St.", "sv.", "Svatí", "Svatý"},
            {"Sr.", "sr.", "st.", "starší"},
            {"Jr.", "jr.", "ml.", "mladší"}
        ],
    }

namegen se automaticky snaží odstranit nehodící se tvary (Svatá, Svaté, ...). Na základě přislušnosti
 jména v dané gramatice. "P:::M" značí, že se má použít pro mužská jména. Obecně jsou tyto možnosti:
 
    P:::F   - ženská jména
    P:::M   - mužská jména
    L   - názvy lokací
    E   - názvy událostí
 

	
## Gramatiky
Gramatiky slouží k určování slov, které se ve jméně skloňují a také určuji druh slova ve jméně (křestní, příjmení...). 

### Formát gramatik
Zde si popíšeme formát souboru s gramatikou.
* První řádek je startovací symbol.
* Zbytek řádků představuje pravidla. Vždy jedno pravidlo na řádku.
  * Formát pravidla: Neterminál -> Terminály a neterminály odděleny bílým znakem
* Startovací symbol je z množiny neterminálů. Znak ε je vyhrazen pro prázdný řetězec.
* Pokud je jako 1. znak v ne/terminálu uveden !, pak se jedná o neohebnou část jména (dědí se dále v derivačním stromu). Pokud je takto označen počíteční neterminál, pak je celá gramatika neohebná a při výpisu je vypsán pouze základní tvar.
* Neterminály mohou být zvoleny libovolně avšak odlišně od terminálů. Nepoužívejte vyhrazené posloupnosti znaků jako jsou: ->,$.
* Je možné používat komentáře, které jsou uvozeny znakem #. Stejně, tak ignoruje prázdné řádky, či řádky, které obsahují pouze komentář.
* Neterminály mohou mít přiřazeny parametry, v takovém případě tvoří šablonu, která bude použita pro vygenerování pravidel. Umožňují kompaktnější a přehlednější zápis množiny pravidel, která se liší pouze v několika málo hodnotách. Více v sekci [Šablony](#šablony).

Terminály jsou předdefinované. Jejich seznam je následující:

	1	- podstatné jméno
	2	- přídavné jméno
	3	- zájméno
	4	- číslovka
	5	- sloveso
	6	- příslovce
	7	- předložka
	7m	- vybrané předložky dalla, de, da, del, di, dos, el, la, le, van, von, O’, ben, bin, y a zu
	7A  - zkrácená předložka nad -> n.
	8	- spojka
	9	- částice
	10	- citoslovce
	t	- titul (Slovo z předem definované množiny)
	r	- římská číslice (od I do XXXIX)
	a	- zkratka
	ia	- Iniciálová zkratka. (Slovo s tečkou na konci o délce 2 [včetně tečky])
	d   - člen/determiner (Příklad: the)
	n	- číslo (pouze z číslic) Příklady: 12., 12
	*   - libovolný token
    q   - část fráze, která se nemá skloňovat (např. New v New York)

Terminálům můžeme přiřazovat atributy. Uvádějí se bezprostředně za terminál do složených závorek. Uvedeme si příklad:

	1{t=G,c=1,n=S,g=M}

Tento zápis říká, že máme podstatné jméno rodu mužského v jednotném čísle, v 1. pádě a druh slova ve jméně je KŘESTNÍ JMÉNO.

Možné atributy a jejich hodnoty:

	g - rod slova    (filtrovací atribut)
		M	mužský životný
	    I	mužský neživotný
	    N	střední
	    F	ženský
	    R	rodina (příjmení)
	n - Mluvnická kategorie číslo.(filtrovací atribut)
		S	jednotné
    	P	množné
    	D	duál
	    R	hromadné označení členů rodiny (Novákovi)
	c - Pád slova.   (filtrovací atribut)
		1	1. pád: Nominativ s pádovými otázkami (kdo, co)
    	2	2. pád: Genitiv (koho, čeho)
    	3	3. pád: Dativ (komu, čemu)
    	4	4. pád: Akuzativ (koho, co)
    	5	5. pád: Vokativ (oslovujeme, voláme)
    	6	6. pád: Lokál (kom, čem)
    	7	7. pád: Instrumentál (kým, čím)
	t - Druh slova ve jméně: Křestní, příjmení atd. (Informační atribut)
		jG	Křestní jméno. Příklad: Petra
    	jS	Příjmení. Příklad: Novák
    	jL	Lokace. Příklad: Brno
    	E	Událost. Příklad: Osvobození Československa
    	R	Římská číslice. Příklad: IV
    	7	Předložka.
    	7a	Například Nové Město n. Moravě
    	8	Spojka.
    	4   číslovka. Příklad: 2
    	jT	Titul. Příklad: prof.
    	I	Iniciálová zkratka. Příklad H. ve jméně John H. White
    	A	Zkratka. Příklad DJ ve jméně DJ Wich
    	GS	Generační specifikace. Příklad: mladší
    	M	Přívlastek/epiteton. Příklad: sličný
    	jB  Jedná se o jméno, které je v historii pevně spjato s jednou osobou. Příklad: Aristotelés
    	jP  ženská patronyma - Albertovna, Vasilijevna
    	jQ  mužská patronyma - Alexandrovič, Alexejevič
    	jI  pseudonymy lidí, např. Šusťa, Švanci, Švícko
    	H   House/Rod Příklad: z Přemyslovců
    	D   člen/determiner (Příklad: the)
    	U	Neznámé
    r - Regulární výraz, který určuje podobu slova.
    	Hodnota musí být vepsána v uvozovkách.
    	
    	Příklad: "^.*ová$"	
    		Všechna slova končící na ová.
    note - Poznámka. Uvedená v morfologické analýze.   (filtrovací atribut)
    	Příklad: jL
    f	-	Flagy
    	GW	- Jedná se o obecné slovo. Jehož lemma začíná malým písmenem a jeho morfologická analýza je bez poznámky.
		NGW - negace GW
		
	p - priorita
    	Výchozí hodnota priority terminálu je 0.
    	Používá se při generování tvarů pro filtrování nechtěných derivací.
    	Příklad:
    		1. derivace: Adam F	P:::M	Adam[k1gMnSc1]#G F[k1gNnSc1]#S ...
	    		Adam	1{p=0, c=1, t=G, g=M, r="^(?!^([sS]vatý|[sS]aint)$).*$", note=jG, n=S}
				F	1{t=S, c=1, p=0, note=jS, g=N, n=S}
    		2. derivace (vítězná): Adam F	P:::M	Adam[k1gMnSc1]#G F#I ...
				Adam	1{p=0, c=1, t=G, g=M, r="^(?!^([sS]vatý|[sS]aint)$).*$", note=jG, n=S}
				F	ia{p=1, t=I}
		
    		Díky prioritě p=1 u F ve druhé derivaci bude vybrána pouze tato derivace.
    		Samotný výběr probíhá tak, že procházíme pomyslným stromem od kořene (první slovo) a postupně, jak procházíme úrovně (slova),
    		tak odstraňujeme větve, kde je menší priorita.
    		Příklad (pouze priority):
    			0 0 0 4
    			2 0 0 0
    			
    			Bude vybrána druhá derivace, protože jsme první odstřihli již při prvním slově, tudiž vyšší priorita není brána v úvahu.

    name_type - druh jména
        Regulární výraz, který určuje podobu druhu slova.
        formát druhu slova:
            Formát řetězce pro jména osob:
                <Type: P=Person>:<Subtype: F/G=Fictional/Group>:<Future purposes: determine regular name and alias>:<Gender: F/M=Female/Male>
            Pro názvy lokací je to jen značka L.
    	
    	Příklad: "P::P:.$"

    l_sep - regulární výraz určující levý separátor
        Například u jména Adam-Philippe de Custine pro slovo Philippe by byl levý separátor -

    r_sep - regulární výraz určující pravý separátor
        Například u jména Adam-Philippe de Custine pro slovo Adam by byl pravý separátor -

Je také možné označit atribut jako volitelný pomocí ?. Příklad:

    note?=jG
    
Uvedený příklad by znamenal, že pokud má slovo v morfologické analýze alespoň jednu poznámku jG (nevezme například jS), pak bude vyžadována. Nicméně pokud v analýze slovo takovou poznámku nemá vůbec, pak se nebere tento argument v potaz (vezme i jS). Toto označení dává smysl u atributů, které jsou filtrovací.
POZOR: Z důvodů rychlejšího zpracovávání se předpokládat pouze jeden volitelný atribut.

### Příklad

    S
	S -> !T_GROUP 1{t=G,c=1,n=S,g=M}
	!T_GROUP -> t{t=T} !T_GROUP	#komentář
	!T_GROUP -> ε
	
### Šablony

Na příkladu si předvedeme jak pomocí parametrů neterminálů a proměnných, které se na ně vážou,  vytvořit šablonu.

Mějme následující pravidla (poslední dvě tvoří šablonu):

	S -> NUM(n=S,g=M)
	S -> NUM(n=P,g=I)
	S -> NUM(c=2,n=S,g=I)
	NUM(c=1,n,g) -> 4{c=$c,t=L,n=$n,g=$g}
	NUM(c=1,n,g) -> ε
	
Obsahují parametrizovaný neterminál NUM, který má 3 parametry: c,n a g. Parametr c má přiřazenou výchozí hodnotu 1 a není nutné jej uvádět, pokud použijeme tento neterminál na prvé straně pravidla.

V pravidle

	NUM(c=1,n,g) -> 4{c=$c,t=L,n=$n,g=$g}

se vyskytují tři proměnné: $c,$n a $g. Každá proměnná se váže k parametru se stejným jménem a začíná znakem $. Uveďme si zde, na jednoduchém příkladě, jakým způsobem se vygenerují pravidla pro následující pravidlo

	S -> NUM(n=S,g=M)

Máme zde neterminál NUM, který se vyskytuje alespoň na jedné levé straně pravidla/šablony. Vyberou se všechna pravidla/šablony na jejichž levé straně se vyskytuje a doplní se dané hodnoty pro n a g, pro c se použije výchozí. Výsledek bude vypadat následovně.

	S->NUM(c=1,g=M,n=S)
	NUM(c=1,g=M,n=S)->4{n=S, g=M, c=1, t=L}
	NUM(c=1,g=M,n=S)->ε
	
Celkově se vygenerují následující pravidla:

	S->NUM(c=1,g=I,n=P)
	S->NUM(c=1,g=M,n=S)
	S->NUM(c=2,g=I,n=S)
	NUM(c=1,g=I,n=P)->4{n=P, g=I, c=1, t=L}
	NUM(c=1,g=I,n=P)->ε
	NUM(c=1,g=M,n=S)->4{n=S, g=M, c=1, t=L}
	NUM(c=1,g=M,n=S)->ε
	NUM(c=2,g=I,n=S)->4{n=S, c=2, g=I, t=L}
	NUM(c=2,g=I,n=S)->ε
	
