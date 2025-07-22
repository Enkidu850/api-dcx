from datetime import datetime


def get_numero_dernier_mois():
    now = datetime.now()
    mois_courant = now.month
    if mois_courant == 1:
        mois_precedent = 12
    else:
        mois_precedent = mois_courant - 1
    return mois_precedent

def get_annee_courante():
    now = datetime.now()
    return now.year

def xml_to_dict(element):
    obj = {}
    for child in element:
        if 'name' in child.attrib and child.attrib['name'] != "":
            obj[child.attrib['name']] = child.text
    return obj