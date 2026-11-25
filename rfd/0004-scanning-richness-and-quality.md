---
authors: Paul van den Braken (@paulvandenbraken), Jordy van den Elshout (@jordy-kennisnet)
date: 24 september 2026
state: draft
discussion: https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/pull/5465
implementation:
labels: boefjes, quality
---

# RFD 0004: Scanreikwijdte en kwaliteit

OpenKAT levert inmiddels voor een groot deel van de scans bruikbare resultaten. In de praktijk zien we dat juist de uitzonderingen relatief veel tijd vragen voor analyse en controle.

Voor verdere uitbreiding van OpenKAT willen we daarom eerst de kwaliteit van de basis verder op orde brengen. De afgesproken basisscan moet voorspelbaar en betrouwbaar functioneren, zodat gebruikers erop kunnen vertrouwen dat deze vindt wat is afgesproken en dat de gerapporteerde findings correct en bruikbaar zijn.

Nieuwe functionaliteiten en aanvullende scanmogelijkheden kunnen daarna voortbouwen op deze stabiele basis.

## Functionele requirements

Binnen deze RFD onderscheiden we drie onderwerpen:

### Scanreikwijdte

- Welke typen kwetsbaarheden, configuratiefouten, software en versies moet de basisscan minimaal kunnen vinden?

### Betrouwbaarheid van het scanproces

- Welke scanners zijn hiervoor nodig, en zijn deze robuust genoeg om met onverwachte input om te gaan?
- Worden fouten in configuratie, bereikbaarheid, boefjes en OpenKAT zelf goed onderscheiden?

### Kwaliteit en accuraatheid van findings

- Is de false-positive-ratio acceptabel?
- Is de severity technisch correct toegepast?
- Wordt een finding alleen als bevestigd gepresenteerd als daarvoor voldoende bewijs is?
- Worden gelijksoortige findings op een bruikbare manier gepresenteerd, zonder onnodige duplicatie en ruis?

De concrete functionele eisen, kwaliteitscriteria en acceptatiecriteria voor deze drie onderwerpen worden in afstemming met de adviesraad verder uitgewerkt.

Daarbij maken we onderscheid tussen de basisscan van OpenKAT en aanvullende boefjes. De basisscan moet zelfstandig aan de afgesproken minimale kwaliteit voldoen.

Aanvullende boefjes kunnen extra of specialistische functionaliteit toevoegen, maar vormen geen voorwaarde om de kwaliteit van de basis te realiseren.

## Non-functional requirements

- Verbeteringen aan scanreikwijdte en kwaliteit mogen niet leiden tot een onacceptabele afname van performance of stabiliteit.
- Wijzigingen aan de basisscan mogen de bestaande kwaliteit niet verslechteren.

## Technisch ontwerp

## Huidige situatie

OpenKat version 1.23rc1

## Github tickets containing aspects of the requested functionality

### Scanreikwijdte:

- #3479: No Software instances found, while they where found using 1.15. Wapalizer regression?, (Jira: OPK-171);
- #4228: Difference findings-reporting between OpenKAT and internet.nl,
  (Jira: OPK-137, closed)
- #4447: Browser plugin of Wapalyzer detects software version while OpenKAT does not,
  (Jira: OPK-171);
- #5136, (closed?): Nikto normalizer silently drops most findings; header-name extraction broken for Nikto 2.6, (Jira: OPK-182;)
- #5302: Extract WordPress software inventory and all vulnerabilities from wpscan
  (geen Jira ticket)

### Betrouwbaarheid van het scanproces

- #4303: False positive report for BAD-Cypher finding,
  (Jira: OPK-119)

### Kwaliteit en accuraatheid van findings

- #4958: Self-configuration of severity levels,
  (Jira: OPK-119)
- #5382: Allow TLS policy to be customizable to allow for different TLS standards
  (Jira: OPK-119)

De bestaande issues geven voorbeelden van onderwerpen die raken aan scanreikwijdte, betrouwbaarheid en kwaliteit. In afstemming met de adviesraad wordt bepaald welke hiervan binnen de basisscan vallen en welke aanvullende functionaliteit betreffen.

## Future improvements

Nieuwe functionaliteiten en aanvullende scanmogelijkheden worden verder ontwikkeld vanuit een stabiele en betrouwbare basis.
