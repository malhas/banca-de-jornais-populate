import xmltodict
import os
import requests
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv

load_dotenv()

MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")
BASE_URL = "https://services.sapo.pt/News/NewsStand/"
ENDPOINTS = ["National", "Sport", "Economy", "International", "Regional", "Magazine"]


def create_object() -> list:
    """
    Creates an object by making a series of HTTP requests to the specified endpoints.

    Returns:
        list: A list of dictionaries representing the created objects.

    """
    capas = []
    for endpoint in ENDPOINTS:
        document = requests.get(BASE_URL + endpoint).text
        dom_dict = xmltodict.parse(document)
        category = dom_dict["newsstand"]["name"]
        for element in dom_dict["newsstand"]["bj_editionsgroup"]["bj_related_image"]:
            capa = {
                "name": element["name"],
                "link": element["link"],
                "image_url": element["image_url"],
                "publish_date": element["publish_date"],
                "item_id": element["id"],
                "category": category,
            }
            capas.append(capa)
    print(f"Found {len(capas)} capas")
    return capas


def populate_db(items: list):
    """
    Populates the database with the given list of items.

    Args:
        items (list): A list of items to be inserted into the database.

    Returns:
        None
    """
    count = 0
    updated = 0
    uri = f"mongodb+srv://admin:{MONGODB_PASSWORD}@cluster0.3goysx3.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(uri, tlsCAFile=certifi.where())
    try:
        client.admin.command("ping")
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)
        exit(1)
    db = client["capasjornais"]
    collection = db["Capas"]
    for item in items:
        dbitem = collection.find_one(
            {"name": item["name"], "publish_date": item["publish_date"], "item_id": item["item_id"]}
        )
        if not dbitem:
            collection.insert_one(item)
            count += 1
        else:
            if item["image_url"] != dbitem["image_url"]:
                collection.update_one(
                    {"name": item["name"], "publish_date": item["publish_date"], "item_id": item["item_id"]},
                    {"$set": item},
                )
                updated += 1

    print(f"Inserted {count} capas and updated {updated} capas")


def main():
    """
    Executes the main functionality of the program.

    This function calls the `create_object` function to create an object and stores it in the `capas` variable. Then it calls the `populate_db` function to populate the database with the `capas` object.

    Parameters:
    - None

    Returns:
    - None
    """
    capas = create_object()
    populate_db(capas)


if __name__ == "__main__":
    main()
