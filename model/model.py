from database.parco_DAO import ParcoDAO
from database.escursione_DAO import EscursioneDAO
from database.punto_interesse_DAO import PuntoInteresseDAO

class Model:
    def __init__(self):
        self.escursioni_map = {}        # Mappa ID escursione -> oggetti Escursione
        self.punti_interesse_map = {}   # Mappa ID punto di interesse -> oggetti PuntoInteresse

        self._pacchetto_ottimo = []
        self._valore_ottimo: int = -1
        self._costo = 0

        # Attributi di appoggio per la ricorsione (così non cambiamo la firma di _ricorsione)
        self._escursioni_parco = []
        self._max_giorni = None
        self._max_budget = None

        # Caricamento
        self.load_escursioni()
        self.load_punti_interesse()
        self.load_relazioni()

    @staticmethod
    def load_parchi():
        """ Restituisce tutti i parchi disponibili """
        return ParcoDAO.get_parchi()

    def load_escursioni(self):
        """ Carica tutte le escursioni in un dizionario [id, Escursione]"""
        self.escursioni_map = EscursioneDAO.get_escursioni()

    def load_punti_interesse(self):
        """ Carica tutti i punti di interesse in un dizionario [id, PuntoInteresse]"""
        self.punti_interesse_map = PuntoInteresseDAO.get_punti_interesse()

    def load_relazioni(self):
        """
            Interroga il database per ottenere tutte le relazioni fra escursioni e punti di interesse e salvarle nelle strutture dati
            Collega escursione <-> punti di interesse.
            --> Ogni Escursione ha un set di PuntoInteresse.
            --> Ogni PuntoInteresse ha un set di Escursioni.
        """
        relazioni = EscursioneDAO.get_escursioni_punti_interesse()
        if relazioni is None:
            return

        for rel in relazioni:
            escursione = self.escursioni_map.get(rel["id_escursione"])
            punto = self.punti_interesse_map.get(rel["id_punto_interesse"])

            # Collego entrambi i lati della relazione N:N usando gli oggetti veri (ORM)
            if escursione is not None and punto is not None:
                escursione.punti_interesse.add(punto)
                punto.escursioni.add(escursione)

    def genera_pacchetto(self, id_parco: str, max_giorni: int = None, max_budget: float = None):
        """
        Calcola il pacchetto di escursioni ottimale per un parco rispettando i vincoli di durata, budget e punti di interesse unici.
        """
        self._pacchetto_ottimo = []
        self._costo = 0
        self._valore_ottimo = -1

        # 1. Filtro solo le escursioni del parco scelto dall'utente
        self._escursioni_parco = [
            e for e in self.escursioni_map.values() if e.id_parco == id_parco
        ]

        # 2. Salvo i vincoli (possono essere None = nessun limite)
        self._max_giorni = max_giorni
        self._max_budget = max_budget

        # 3. Faccio partire la ricorsione da indice 0, zaino vuoto, costi/valori a 0 e set vuoto
        self._ricorsione(
            start_index=0,
            pacchetto_parziale=[],
            durata_corrente=0,
            costo_corrente=0.0,
            valore_corrente=0,
            punti_usati=set()
        )

        return self._pacchetto_ottimo, self._costo, self._valore_ottimo

    def _ricorsione(self, start_index: int, pacchetto_parziale: list, durata_corrente: int, costo_corrente: float, valore_corrente: int, punti_usati: set):
        """ Algoritmo di ricorsione che deve trovare il pacchetto che massimizza il voto complessivo dei visitatori"""

        # 🟤 A - DO ALWAYS: ogni pacchetto che arriva qui è già valido.
        # Controllo subito se batte il record attuale.
        if valore_corrente > self._valore_ottimo:
            self._valore_ottimo = valore_corrente
            self._costo = costo_corrente
            self._pacchetto_ottimo = pacchetto_parziale.copy()  # 🚨 .copy() obbligatorio!

        # 🟢 B - TERMINAL CONDITION: non serve un if esplicito, perché il for sotto
        # si ferma da solo quando start_index arriva in fondo alla lista.

        # Ciclo solo da start_index in poi: evita escursioni duplicate e combinazioni ripetute ([A,B] vs [B,A])
        for i in range(start_index, len(self._escursioni_parco)):
            escursione = self._escursioni_parco[i]

            # 🟡 C - FILTER (Controllo i 3 vincoli prima di aggiungere l'escursione)
            # 1. Vincolo durata
            if self._max_giorni is not None and durata_corrente + escursione.durata_giorni > self._max_giorni:
                continue

            # 2. Vincolo budget
            if self._max_budget is not None and costo_corrente + escursione.costo > self._max_budget:
                continue

            # 3. Vincolo punti di interesse unici (isdisjoint = nessun elemento in comune)
            if not punti_usati.isdisjoint(escursione.punti_interesse):
                continue

            # 🔵 D - COMPUTE PARTIAL (Sporco lo stato)
            valore_escursione = sum(p.voto_visitatori for p in escursione.punti_interesse)
            pacchetto_parziale.append(escursione)
            punti_usati.update(escursione.punti_interesse)

            # 🔴 E - RECURSION (Scendo in profondità passando i + 1)
            self._ricorsione(
                start_index=i + 1,
                pacchetto_parziale=pacchetto_parziale,
                durata_corrente=durata_corrente + escursione.durata_giorni,
                costo_corrente=costo_corrente + escursione.costo,
                valore_corrente=valore_corrente + valore_escursione,
                punti_usati=punti_usati
            )

            # 🟣 F - BACKTRACKING (La gomma da cancellare: pulisco sia lista che set)
            pacchetto_parziale.pop()
            punti_usati.difference_update(escursione.punti_interesse)
