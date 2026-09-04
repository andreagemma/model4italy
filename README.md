# Model4Italy

Model4Italy è uno strumento avanzato per la meso-simulazione e l'analisi del traffico veicolare su scala urbana e regionale. Grazie ai file di configurazione di tipo JSON e INI, è possibile personalizzare parametri come la rete stradale, la domanda di traffico, le regole di circolazione e le strategie di controllo. Model4Italy supporta l'integrazione con dati reali e offre strumenti per la visualizzazione e l'analisi dei risultati, facilitando il processo decisionale per enti pubblici, ricercatori e professionisti del settore.

## Compatibilita piattaforme

- Supportato: Windows, Linux, macOS

Le pipeline CI del progetto validano le installazioni su Windows, Linux e macOS.

## Installazione
Installare la versione di python 3.12.
Installare le librerie presenti in ```requirements.txt```

### Dipendenza GDAL (obbligatoria)

Model4Italy dipende da GDAL. Installare GDAL separatamente seguendo la documentazione ufficiale:

- https://gdal.org/en/stable/download.html

- come libreria di sistema (libgdal)
- come pacchetto Python (`gdal`)

Su macOS installare anche Fiona, seguendo la documentazione ufficiale:

- https://fiona.readthedocs.io/

Le due versioni devono essere compatibili tra loro (stessa major/minor, e in generale la stessa versione).

Se è la prima volta che viene eseguito il sistema sulla macchina e non è presente il file ```model4italy.db``` necessario come database interno della piattaforma eseguire il comando:
```sh
python -m m4i init_db
```

## Avvio del programma

Per eseguire il programma principale:

```sh
python -m m4i
```
il programma in automatico:
 * leggerà il file ```settings.ini``` per la configurazione dei parametri del software.
 * leggera il file ```params.json``` per la configurazione dei parametri di simulazione.
 * leggera il file ```params_data.json``` per la configurazione dei dati di input e output per la simulazione (solo se presente).

i file ```params.json``` e ```params_data.json``` sono complementari e vengono fusi in un unico file di configurazione dal sistema.


Più in generale il programma può essere eseguito con i seguenti parametri:
```sh
python -m m4i run -p nome_file_params.json -d nome_file_params_data.json -c nome_file_settings.ini
```

Per avviare il programma in modalità server eseguire
```sh
python -m m4i server
```

In alternativa è possibile importare la libreria e usare i seguenti comandi:

```python
import m4i

m4i.init_db()
```

oppure

```python
import m4i

m4i.run(params="params.json", params_data="params_data.json")
```

oppure passare i parametri come dictionary python

```python
import m4i

params= { 
        "simulation_id": 1,
        "scenario": "eur2",
        "start": "07:00",
        "end": "07:30",  
        "op": "assignment",
        "settings": {
            "MSA_MAX_ITE": 6,
            "MSA_K": 2
        },
    }

m4i.run(params=params, params_data="params_data.json")

params = { 
        "simulation_id": 1,
        "scenario": "eur2",
        "start": "07:00",
        "end": "07:30",  
        "op": "assignment"
    }
settings= { 
        "settings": {
            "MSA_MAX_ITE": 1,
            "MSA_K": 2
        }
    }


m4i.run(params=[params, settings], params_data="params_data.json")

m4i.run(params=[params, settings, "params_data.json"])

m4i.run(params=["params.json", params, settings], params_data="params_data.json")
# Descrizione del file di configurazione unificato (params.json + params_data.json)


Quando Model4Italy viene avviato, i file `params.json` e `params_data.json` vengono uniti in un unico oggetto di configurazione. Questo file risultante contiene sia i parametri generali della simulazione sia tutte le specifiche relative ai dati di input/output, domanda, rete, eventi, ecc.

## Struttura generale

```json
{
    "simulation_id": 25,
    "scenario": "Demo",
    "date": "2024-05-07",
    "start": "07:00",
    "end": "7:30",
    "op": "assignment",
    "scenario_id": 1,
    "settings": {
        "MSA_MAX_ITE": 6,
        "MSA_SPP_NUMCPUS": 0,
        "MSA_K": 3
    },
    "params": {
        // Tutti i parametri provenienti da params_data.json
    }
}
```

## Descrizione dei principali campi

- **simulation_id**: Identificativo numerico della simulazione (del chiamante).
- **description**: Descrizione testuale della simulazione (opzionale).
- **date**: Data di riferimento della simulazione.
- **start**: Ora di inizio della simulazione (formato HH:MM).
- **end**: Ora di fine della simulazione (formato HH:MM).
- **op**: Operazione principale da eseguire (es. `assignment`).
- **scenario_id**: Identificativo dello scenario di rete/dati da utilizzare.
- **settings**: Parametri avanzati per la simulazione (es. numero massimo di iterazioni, CPU, ecc.).
- **params**: Oggetto che contiene tutte le informazioni dettagliate sui dati di input/output, domanda, rete, eventi, risultati, ecc.  
  La struttura interna di `params` dipende dal tipo di simulazione e dalla sorgente dati (file, database, ecc.).

  I campi opzionali possono essere usati per comporre configurazioni parametriche come di seguito

### Esempio di struttura interna di `params`

```json
"params": {
    "input": {
        "connector": "FileLoader",
        "location": "./dati/GrafoEur"
    },
    "output": {
        "connector": "FileWriter",
        "location": "./dati/output/{description}"
    },
    "modes": [
        {
            "id": "c",
            "description": "car",
            "eq_factor": 1
        },
        {
            "id": "h",
            "description": "heavy",
            "eq_factor": 2
        }
    ],
    "demand": [
        {
            "mode": "c",
            "matrices": [
                "mat_car.parquet"
            ]
        }
    ],
    "zones": {
        "connector": "FileLoader",
        "src": "dati/GrafoEur/zones.shp"
    },
    "supply": [
        {
            "links": "eur_links.shp",
            "nodes": "eur_nodes.shp",
            "turns": "turns_proh.csv"
        }
    ],
    "links_sets": [ ... ],
    "events": [ ... ],
    "detectors": [ ... ],
    "traffic_lights": [ ... ],
    "aggregated_results": "...",
    "paths": "...",
    "state": "..."
}
```

## Note

- I parametri di `params.json` hanno priorità su quelli di `params_data.json` in caso di conflitto.
- Il campo `params` può contenere riferimenti a file, query SQL, mapping di colonne, parametri di scenario, ecc.
- Le variabili tra parentesi graffe (es. `{description}`, `{simulation_id}`) vengono sostituite automaticamente dal sistema in fase di esecuzione.

Per dettagli sulla struttura dei singoli campi di `params`, fare riferimento agli esempi forniti nei file `params_data_*.json` e alla documentazione interna.


# Descrizione del file settings.ini

Il file `settings.ini` contiene tutte le impostazioni di configurazione per Model4Italy. Di seguito una panoramica delle sezioni e dei parametri disponibili.

---

## [GENERAL]
- **SRC_COEFS**: Percorso al file dei coefficienti per la valutazione degli eventi (default: coefficients.json).
- **SRC_CONV_TBL**: Percorso alla tabella di conversione (opzionale) (default: None).
- **DEBUG**: Abilita/disabilita la modalità debug (`True`/`False`) (defualt: False).
- **CRS**: Sistema di riferimento delle coordinate del progetto (default: `EPSG:4326`).
- **CRS_CALC**: Sistema di riferimento locale delle coordinate per i calcoli (default: `EPSG:6875`).

---

## [OUTPUT]
- **AGG_INT**: Intervallo di aggregazione dei risultati in minuti (default:15)..
- **OUTPUT_STATE_COMPRESSION**: Metodo di compressione per la memorizzazione dello stato (default: None).
- **OUTPUT_STATE_LEVEL_COMPRESSION**: Livello di comrpressione (default: 5)
---

## [WEB_SERVER]
- **WEB_SERVER_HOST**: Indirizzo host del server web (default: localhost).
- **WEB_SERVER_PORT**: Porta del server web.
- **WEB_SERVER_DEBUG**: Abilita/disabilita la modalità debug per il server web.

---

## [DATABASE]
- **DATABASE_URL**: Stringa di connessione al database interno (es. `sqlite:///model4italy.db`).

---

## [DATABASE_SETTINGS]
- **DB_SETTINGS_USE**: Abilita/disabilita l’uso database per i dati di settings (in integrazione al presente file).
- **DB_SETTINGS_TYPE**: Tipo di database (`sqlite`, `postgresql`, ecc.).
- **DB_SETTINGS_DRIVER**: Driver del database.
- **DB_SETTINGS_USER**: Nome utente del database.
- **DB_SETTINGS_PASS**: Password del database.
- **DB_SETTINGS_HOST**: Host del database.
- **DB_SETTINGS_PORT**: Porta del database.
- **DB_SETTINGS_NAME**: Nome del database.

---

## [LOGGING]
- **LOG_USE**: Abilita/disabilita il logging.
- **LOG_NAME**: Nome del logger.
- **LOG_LEVEL**: Livello di logging (`DEBUG`, `INFO`, ecc.).
- **LOG_EXECUTION_FORMAT**: Formato del log per l’esecuzione.
- **LOG_FORMAT**: Formato standard del log.
- **LOG_DIR**: Directory dove salvare i log.
- **LOG_ON_DATABASE**: Salva i log anche sul database.
- **LOG_ON_CONSOLE**: Mostra i log sulla console.
- **LOG_ON_FILE**: Salva i log su file.

---

## [IPC]
- **IPC_USE**: Abilita/disabilita la comunicazione inter-processo.
- **IPC_BUKCET**: Nome del bucket IPC.
- **IPC_BACKEND**: Backend utilizzato (`local` o `redis`).
- **IPC_HOST**: Host del backend IPC.
- **IPC_PORT**: Porta del backend IPC.
- **IPC_DB**: Numero del database Redis (se usato).
- **IPC_COMPRESSION**: Metodo di compressione per il trasferimento dati.
- **IPC_COMPRESSION_LEVEL**: Livello di compressione (1-9).

---

## [PARALLEL]
- **PARALLEL_USE**: Abilita/disabilita l’esecuzione parallela.
- **PARALLEL_NUMCPUS**: Numero di processi paralleli.
- **PARALLEL_ENGINE**: Motore di parallelizzazione (`ray` o `None`).
- **PARALLEL_CLUSTER_ADDRESS**: Indirizzo del cluster di calcolo.

---

## [SIMULATOR]
- **SIMU_STEP**: Passo di simulazione (in secondi).
- **CAR_LENGTH**: Lunghezza media dei veicoli (in metri).
- **MIN_SPEED**: Velocità minima consentita (in km/h).
- **LT1**, **LT2**: Parametri aggiuntivi per la simulazione.

---

## [ASSIGNMENT]
- **CLASS_EQ_FACT**: Fattori di equivalenza di default per le classi di veicoli.
- **MSA_MAX_ITE**: Numero massimo di iterazioni MSA.
- **MSA_RGAP**: RGAP per la convergenza MSA.
- **MSA_K**: Numero di cammini alternativi.
- **MSA_MAX_TIMESLICE**: Massima durata di una slice temporale.
- **MSA_SPP_NUMCPUS**: Numero di CPU per SPP.
- **MSA_K_BALANCING**: <=0 indica che che il bilanciamento dell'MSA inizia con k=MSA_K >0 indica che k=valore inidcato
- **DELTA_T**: Intervallo temporale per l’assegnazione.
- **SAVE_PATHS**, **LOAD_PATHS**: Salva/carica i cammini.
- **SAVE_GRAPH**, **LOAD_GRAPH**: Salva/carica il grafo.
- **MSA_PRELOAD**, **MSA_POSTLOAD**: Pre/post-caricamento dati.

---

## [OD_ESIMATION]
- **OD_ESTIMATION_WHISKERS**: Pre-caricamento dati OD (in minuti).
- **OD_ESTIMATION_MAX_ITE**: Iterazioni massime per la stima OD.
- **OD_ESTIMATION_RGAP**: RGAP per la stima OD.
- **OD_ESTIMATION_MSA_MAX_ITE**: Iterazioni massime MSA per OD.
- **OD_ESTIMATION_MSA_K**: Numero di cammini MSA per OD.
- **OD_ESTIMATION_MSA_RGAP**: RGAP MSA per OD.
- **OD_ESTIMATION_MSA_TIMESLICE**: Timeslice MSA per OD.

---

## [FCD]
- **FCD_SERVER_FCD_TIMESLICE**: Intervallo di esecuzione della procedura di analisi FCD (in minuti).
- **FCD_SERVER_FCD_HORIZON**: Orizzonte temporale per la memorizzazione dati FCD (in minuti).
- **FCD_MAP_MATCHING_CPUS**: CPU per il map matching.
- **FCD_ROUTING_CPUS**: CPU per il path matching.
- **FCD_MAP_MATCHING_MAX_DISTANCE**: Distanza massima per il map matching (in metri).
- **FCD_MAP_MATCHING_MAX_ANGLE**: Angolo massimo per il map matching (in gradi).
- **FCD_ROUTING_START_FROM_ZONE**: Abilita inizio cammini dal centroide.
- **FCD_ROUTING_END_TO_ZONE**: Abilita fine cammini al centoride.
- **FCD_ROUTING_AGGRATION_INTERVAL**: Intervallo di aggregazione cammini (in minuti).

---
