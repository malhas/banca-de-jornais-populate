import xmltodict
import os
import requests
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
import tweepy
from tweepy.errors import TwitterServerError

load_dotenv()

MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")


def create_object() -> list:
    capas = []
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
    capas = list(collection.find({}))
    return capas


def populate_db(items: list) -> list:
    uri = f"mongodb+srv://admin:{MONGODB_PASSWORD}@cluster0.3goysx3.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(uri, tlsCAFile=certifi.where())
    try:
        client.admin.command("ping")
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)
        exit(1)
    db = client["capasjornais"]
    collection = db["Covers"]
    for item in items:
        print(f"Inserting {item['name']} {item['publish_date']} edition into database...")
        dbitem = collection.find_one({"item_id": item["item_id"]})
        if not dbitem:
            new_item = {
                "name": item["name"],
                "editions": [{"publish_date": item["publish_date"], "image_url": item["image_url"]}],
                "link": item["link"],
                "item_id": item["item_id"],
                "category": item["category"],
            }
            collection.insert_one(new_item)
            print("New item inserted!")
        else:
            collection.update_one(
                {"item_id": item["item_id"]},
                {
                    "$push": {
                        "editions": {
                            "$each": [{"publish_date": item["publish_date"], "image_url": item["image_url"]}],
                            "$position": 0,
                        }
                    }
                },
            )
            print("Added new edition!")


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
