import threading
import time
import datetime
import pandas as pd
import requests
from sqlalchemy import create_engine
from sqlalchemy import text
from convertjson import converter
from json import loads, dumps

from dictionnaires import col_patr_bat, col_patr, col_patr_site, col_synthesis
from params import target_db, api_login, api_pwd
from utils import get_numero_dernier_mois, get_annee_courante

TOKEN = ""
empty_json = "[]"
url_patrimony = "https://deltaconsoexpert.hellio.com/Services/v1/Patrimony/Export"
url_synthesis = "https://deltaconsoexpert.hellio.com/Services/v1/Synthesis/DeliveryPoint"

def detect_and_convert_types(lst:list[str]) -> list:
    """
        Convertit les strings en leurs types réels
    """
    converted_list = []
    for item in lst:
        if item == "":
            converted_list.append(None)
        elif item.lower() == "true":
            converted_list.append(True)
        elif item.lower() == "false":
            converted_list.append(False)
        elif item and (item.replace('.', '', 1).isdigit() or (item[0] == '-' and item[1:].replace('.', '', 1).isdigit())):
            if '.' in item:
                converted_list.append(float(item))
            else:
                converted_list.append(int(item))
        elif item and (item.replace(',', '', 1).isdigit() or (item[0] == '-' and item[1:].replace(',', '', 1).isdigit())):
            converted_list.append(float(item.replace(',', '.')))
        else:
            converted_list.append(item)
    return converted_list

def replace_element_in_list(lst:list, old_element:str, new_element) -> list:
    """
        Remplace un élément dans une liste par un autre
    """
    return [new_element if x == old_element else x for x in lst]


def load_synthesis_delivery_point() -> None:
    print("load synthesis delivery point")
    json_data = []
    query_params = {
        'token': TOKEN,
        'format': 'JSON'
    }

    engine = create_engine(target_db, echo=True)

    with engine.connect() as con:
        query = text('SELECT distinct(invariant) FROM cadastre_solaire.patrimony LIMIT 1000')
        query_count = text('SELECT count(distinct(invariant)) FROM cadastre_solaire.patrimony')
        result = con.execute(query)
        result_count = con.execute(query_count)

        invariants = [row[0] for row in result]
        count:int = result_count.fetchone()[0]

    dernier_mois = get_numero_dernier_mois()
    annee = get_annee_courante()

    dico = {}
    nb = 1

    """
        Boucle sur tous les invariants pour récupérer les données associées
        Des invariants sont susceptibles de ne pas posséder de données
        Ils sont remplacés par "inconnu" pour éviter de faire planter le script
    """
    for i in invariants:
        if i is None:
            i = "inconnu"

        # test sur Janvier 2023
        body = {
            "Invariants": [i],
            "SynthesisType": "Invoice",
            "Periodicity": "Month",
            "StartingMonth": 1,#dernier_mois,
            "EndingMonth": 1,#dernier_mois,
            "StartingYear": 2023,#annee,
            "EndingYear": 2023,#annee,
            "SlidingLastYear": False,
            "WithoutEstimated": True,
            "UseDJUCorrectors": False,
            "DJUCorrectors": [],
            "Threshold": 10,
            "NbElement": 200,
            "PageNumber": 1
        }

        # Convertit le dictionnaire en JSON (le JSON n'accepte pas les simples quotes et les True/False en majuscules)

        body = str(body).replace("'", '"')
        body = body.replace("True", "true")
        body = body.replace("False", "false")

        #print(body)
        etat = ""

        try:
            r = requests.post(url_synthesis, params=query_params, data=body, headers={'Content-Type': 'application/json'})
            r.raise_for_status()
            json_data:list[dict] = r.json() # Structure : [{...}]
            json_data:dict = json_data[0] #Structure : {...}
            # Sépare les clefs et les valeurs dans deux listes distinctes
            data_keys:list[str] = list(json_data.keys())
            data_values:list[str] = list(json_data.values())
            # Boucle sur toutes les clés et valeurs pour les ajouter au dictionnaire
            if dico == {}:
                for key in data_keys:
                    dico[key] = []
            for key, value in zip(dico.keys(), data_values):
                dico[key].append(value)
            """
                dico est un dictionnaire qui contient toutes les données organisées par colonnes
                Il est plus tard transformé en dataframe pour l'envoyer dans la base de données
                Structure : {colonne1: [valeur1, valeur2, ...], colonne2: [valeur1, valeur2, ...], ...}
                Les colonnes sont ajoutées au premier appel, les données sont ajoutées au fur et à mesure sur tous les appels
                Les colonnes sont plus tard renommées pour correspondre à la structure de la base de données
            """
            print("Requête terminée...")
            etat = "réussie"
        except requests.exceptions.HTTPError as errh:
            if errh.response.status_code == 401:
                print("expiration du token => renouvellement")
                refresh_token()
                query_params = {'token': TOKEN, 'format': 'JSON'}

                try:
                    r = requests.post(url_synthesis, params=query_params, data=body, headers={'Content-Type': 'application/json'})
                    r.raise_for_status()
                    json_data = r.json()
                    json_data = json_data[0]
                    data_keys = list(json_data.keys())
                    data_values = list(json_data.values())
                    if dico == {}:
                        for key in data_keys:
                            dico[key] = []
                    for key, value in zip(dico.keys(), data_values):
                        dico[key].append(value)
                    print("Requête terminée...")
                    etat = "réussie"

                except requests.exceptions.HTTPError as errh:
                    if errh.response.status_code == 400:
                        etat = "échouée"
                        if i == "inconnu":
                            print("Aucun PDL trouvé")
                        else:
                            print("Probablement pas de données pour le PDL : " + i)
                    else:
                        etat = "échouée"
                        print("HTTP Error:", errh)

            elif errh.response.status_code == 400:
                etat = "échouée"
                if i == "inconnu":
                    print("Aucun PDL trouvé")
                else:
                    print("Probablement pas de données pour le PDL : " + i)
            else:
                etat = "échouée"
                print("HTTP Error:", errh)

        print("collecte "+etat+" : " + i)
        print("PDL : " + str(nb) + "/" + str(count))
        nb += 1
    
    for liste in dico:
        dico[liste] = detect_and_convert_types(dico[liste])

    # Conversion de dico en dataframe et renommage des colonnes
    df = pd.DataFrame(dico)
    df.rename(columns=col_synthesis, inplace=True)
    df.index.names = ['id']

    df.to_sql(name='synthesis_delivery_point', con=engine, schema='cadastre_solaire', if_exists="replace")

def load_table(nom:str, nom_table:str, typelist:str, colonnes:dict, url:str) -> None:
    """
        Fonction qui charge les données dans la base de données
        Permet de charger les données des tables patrimony, patrimony_bat et patrimony_site
        :param nom: Nom de la table à charger
        :param nom_table: Nom de la table dans la base de données
        :param typelist: Liste des types d'objets à charger
        :param colonnes: Dictionnaire de correspondance entre les colonnes de l'API et celles de la base de données
        :param url: URL de l'API à interroger
    """

    print("load", nom)

    json = ""
    page = 1

    engine = create_engine(target_db, echo=True)
    print("suppression de la table", nom)
    with engine.connect() as con:
        # Suppression de la table si elle existe déjà pour pouvoir mettre à jour les données
        try:
            con.execute(text("BEGIN"))
            con.execute(text("DELETE FROM cadastre_solaire." + nom_table))
            con.execute(text("COMMIT"))
            print("Contenu de la table", nom,"supprimé.")
        except Exception as e:
            con.execute(text("ROLLBACK"))
            print(f"Erreur lors de la suppression des données : {e}")

    # Boucle sur toutes les pages de l'API (1 page = 1000 lignes)
    while json != empty_json:
        query_params = {
            'token': TOKEN,
            'typesList': typelist,
            'format': 'JSON',
            'pageNumber': page
        }
        print("Lancement de la requête page", page, "...")
        try:
            r = requests.get(url, params=query_params)
            r.encoding = 'UTF-8'
        except requests.exceptions.HTTPError as errh:
            if errh.response.status_code == 401:
                print("expiration du token => renouvellement")
                refresh_token()
                query_params = {
                    'token': TOKEN,
                    'typesList': typelist,
                    'format': 'JSON',
                    'pageNumber': page
                }
                r = requests.get(url, params=query_params)
                r.encoding = 'UTF-8'
            else:
                print("HTTP Error:", errh)

        print("Requête terminée...")
        r.raise_for_status()
        print(r.status_code)

        json = r.json()

        if json == []:
            print("Aucune donnée à traiter")
            break

        try:
            donnees = loads(r.text)
        except UnicodeDecodeError:
            data_str = json.dumps(json, ensure_ascii=False)
            print(data_str)

        editable = []
        value = []
        type = []

        cols = []
        for element in json:
            names = list(element.keys())
            cols += names

        # Tri des valeurs importantes: Editable (True ou False) (inutile), Value (strings), Type (strings) (inutile)
        for donnee in donnees:
            for clef in donnee:
                editable.append(donnee[clef]["Editable"])
                value.append(donnee[clef]["Value"])
                type.append(donnee[clef]["Type"])

        # Permet de détecter le type de chaque valeur et de les convertir en leur type réel
        # Exemple : "1" devient 1, "true" devient True, "false" devient False, "12.5" devient 12.5
        true_value = detect_and_convert_types(value)

        dico = {}
        for n, t in zip(cols, true_value):
            if n in dico:
                dico[n].append(t)
            else:
                dico[n] = [t]
        """
            dico est un dictionnaire qui contient toutes les données organisées par colonnes
            Il est plus tard transformé en dataframe pour l'envoyer dans la base de données
            Structure : {colonne1: [valeur1, valeur2, ...], colonne2: [valeur1, valeur2, ...], ...}
            Les colonnes sont ajoutées au premier appel, les données sont ajoutées au fur et à mesure sur tous les appels
            Les colonnes sont plus tard renommées pour correspondre à la structure de la base de données
        """

        # Corrige les données qui ne sont pas correctes
        if "AUBIGNY-LES CLOUZEAUX" in dico["PostalCode"]:
            dico["PostalCode"] = replace_element_in_list(dico["PostalCode"], "AUBIGNY-LES CLOUZEAUX", None)
        elif "LESMAGNILSREIGNIERS" in dico["PostalCode"]:
            dico["PostalCode"] = replace_element_in_list(dico["PostalCode"], "LESMAGNILSREIGNIERS", None)
        elif "LES MAGNILS REIGNIERS" in dico["PostalCode"]:
            dico["PostalCode"] = replace_element_in_list(dico["PostalCode"], "LES MAGNILS REIGNIERS", None)
        for code in range(len(dico["PostalCode"])):
            if " " in str(dico["PostalCode"][code]):
                try:
                    dico["PostalCode"][code] = int(str(dico["PostalCode"][code]).replace(" ", ""))
                except ValueError:
                    dico["PostalCode"][code] = None

        df = pd.DataFrame(dico)

        # Renommage des colonnes
        df.rename(columns=colonnes, inplace=True)
        df.columns = df.columns.str.replace('é', 'e')
        df.columns = df.columns.str.replace('É', 'E')
        df.index.names = ['id']

        df.apply(lambda x: x.str.encode('utf-8').str.decode('utf-8') if x.dtype == 'object' else x)
        df.to_sql(name=nom_table, con=engine, schema='cadastre_solaire', if_exists="append")

        page += 1

def refresh_token():
    print("refresh token")
    print("Current time: ", time.ctime())
    response = requests.post("https://deltaconsoexpert.hellio.com/Token/v1/Token", json={
        "login": api_login,
        "password": api_pwd,
        "grant_type": "authorization_code"
    })
    global TOKEN
    TOKEN = response.text.strip('\"')
    print(TOKEN)


if __name__ == "__main__":

    # Auth
    if not TOKEN:
        response = requests.post("https://deltaconsoexpert.hellio.com/Token/v1/Token", json={
            "login": api_login,
            "password": api_pwd,
            "grant_type": "authorization_code"
        })
        TOKEN = response.text.strip('\"')
    print(TOKEN)
    now = datetime.datetime.now()
    print("start : " + str(now.time()))
    #load_table("patrimony", "patrimony", "Compteur électrique", col_patr, url_patrimony)
    #load_table("patrimony bâtiment", "patrimony_batiment", "Bâtiment", col_patr_bat, url_patrimony)
    #load_table("patrimony site", "patrimony_site", "Site", col_patr_site, url_patrimony)
    #load_synthesis_delivery_point()
    now = datetime.datetime.now()
    print("fin du script : " + str(now.time()))
