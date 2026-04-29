## Attività generali
* FS Tech
* Jarvice
* FBK
* Aggiornare documentazione

## Attività d svolgere
- [x] Clustering Cammini OFF Line
- [x] Assegnazione con Cammini FCD Precalcolati OFFLIne
- [x] Salvataggio dati micro di simulazione
- [x] Salvataggio dati stats
- [x] Salvataggio dati intersezione
- [ ] Calolare Speed dopo analisi OffLine o salvataggio offline
- [ ] Aggiungere dt_o e dt_d ai paths del rt_server
- [ ] Calcolo e salvataggio splitting rates di arco
- [ ] Correggere formato cammini offline secondo specifiche DB
- [ ] Stima OD Online con gestione day_type
- [ ] Stima OD Offline con gestione day_type
- [ ] Rolling Horizon con gestione day_type (reset grafo) con timestamp di avvio a scelta
- [ ] Sperimentare modello oltre la mezzanotte e provare grafo unico 24 ore
- [ ] Aggregazione Grafo FCD OFF Line ma prima aggiungere lista istanti temporali di riferiemnto (day_type come metadato)
- [ ] Aggregazione Grafo FCD On Line
- [ ] Uso delle velocità di grafo online (Natalia)
- [ ] Calcolo Cammini On Line e loro utilizzo. Nodi di diversione
- [ ] Fare una Operazione per calcolare i cammini offline on demand sui risultati di un'assegnazione
- [ ] Gestire variazioni temporali dei modi ammessi
- [ ] Prendere manovre da grafo OSM
- [ ] Usare grafo OSM
- [ ] Implementazione Eventi
    - [ ] - Chiusure di strade
    - [ ] - Chiusure di corsie
    - [ ] - Eventi meteo
    - [ ] - Limiti di velocità
    - [ ] - Chisura a classi di Veicolo
- [ ] Assegnazione multi-classe (Natalia)
- [ ] Salvataggio su DB con prequery
- [ ] Modi di trasporto da file o db
- [ ] Verificare opzioni aggiuntive per connettori
    - [ ] - CRS
    - [ ] - layer per gpkg
    - [ ] - prequery
    - [ ] - postquery 
    - [ ] - parametri di lettura
    - [ ] - tz_data
    - [ ] - index_col
- [ ] Fare un modello di analisi
- [ ] Provare assegnazione che calcola flussi di cammino anche sulle manovre e sui nodi
- [x] Inserire manovre di svolta ARCO-ARCO rinunciato a causa dei problemi di selezione su QGIS
- [ ] Introdurre aparametri sul modello di assegnazione e sulla scelta del modello di caricamento da usare. Correggere modelli di caricamento statici e quasi dinamici
- [x] PRovare a implementare il file_reader con io_daskdataframe. Fatto ma con altro
- [ ] RiFare offline_map_mathing usando le giuste opzioni di FCDServer
- [ ] prevedere params con Dataframe come parametro nel dictionary
- [ ] Pensare a come trasformare tutto in una libreria per usare m4i programmaticamente
- [ ] testare settings via db
- [ ] Adaptive Smoothing Method per dati FCD a livello di rete
- [ ] implementare modello di alert
- [ ] Scrittura asincrona dei risultati
- [ ] Dockerizzare


