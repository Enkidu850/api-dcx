import re
from json import loads
import pandas as pd

test = """{
    "Root": {
        "Objet": [
            {
                "@Name": "compteur",
                "Attribut": [
                    {
                        "#text": "blablablabla"
                    },
                    {
                        "#text": "blablablablabdzjakuba"
                    }
                ]
            },
            {
                "@Name": "compteur2",
                "Attribut": [
                    {
                        "#text": "blablablabla2"
                    },
                    {
                        "#text": "blablablablabdzjakuba2"
                    }
                ]
            }
        ]
    }
}"""

def multiple_spaces(text):
    return bool(re.search(r' {2,}', text))

def remove_multiples_spaces(text):
    return re.sub(r' {2,}', ' ', text)

def converter(json):

    if r"\n" in json:
        json = json.replace(r"\n", "")
    if r"\r" in json:
        json = json.replace(r"\r", "")
    if r"\"" in json:
        json = json.replace(r"\"", "\"")
    if multiple_spaces(json):
        json = remove_multiples_spaces(json)

    return json[1:-1]

if __name__ == "__main__":
    print("Traitement du fichier JSON")

    with open("main_bad_json.txt", "r") as f:
        json_data = f.read()
    #print(json_data)
    
    json_data = converter(json_data) # Enlève les guillemets de début et de fin

    #print(json_data)
    
    with open("good_json.json", "w", encoding="UTF-8") as f:
        f.write("{"+json_data+"}")
    
    print("Traitement termine")
    with open("good_json.json", "r") as f:
        json = loads(f.read())
        print(json["Root"]["Objet"][0]["Attribut"][0]["#text"])

    #test = loads(test)
    #df = pd.DataFrame(test)
    #test["newFeature"] = "test"
    #print(df)
    #print(test)


#print(converter(r"Je m'appelle\r Jean     Dupont\n et j'ai \"30\" ans."))