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
BASE_URL = "https://services.sapo.pt/News/NewsStand/"
ENDPOINTS = ["National", "Sport", "Economy", "International", "Regional", "Magazine"]
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET")
VERCEL_WEBHOOK = os.environ.get("VERCEL_WEBHOOK")

CAPAS = {
    "Expresso": {"twitter": "@expresso", "tags": "#Notícias"},
    "Nascer do SOL": {"twitter": "@solonline", "tags": "#Notícias"},
    "Correio da Manhã": {"twitter": "@cmjornal", "tags": "#Notícias"},
    "Jornal de Notícias": {"twitter": "@jornalnoticias", "tags": "#Notícias"},
    "Público": {"twitter": "@publico", "tags": "#Notícias"},
    "Diário de Notícias": {"twitter": "@dntwit", "tags": "#Notícias"},
    "O Jornal Económico": {"twitter": "@ojeconomico", "tags": "#Economia"},
    "Jornal de Negócios": {"twitter": "@JNegocios", "tags": "#Economia"},
    "O Jogo": {"twitter": "@ojogo", "tags": "#Desporto"},
    "A Bola": {"twitter": "@abolapt", "tags": "#Desporto"},
    "Record": {"twitter": "@Record_Portugal", "tags": "#Desporto"},
    "El País": {"twitter": "@elpais_espana", "tags": "#Noticias"},
    "El Mundo": {"twitter": "@elmundoes", "tags": "#Noticias"},
    "Le Monde": {"twitter": "@lemondefr", "tags": "#Noticias"},
    "Le Figaro": {"twitter": "@Le_Figaro", "tags": "#Noticias"},
    "The Daily Telegraph": {"twitter": "@Telegraph", "tags": "#News"},
    "The Guardian": {"twitter": "@guardian", "tags": "#News"},
    "The Independent": {"twitter": "@independent", "tags": "#News"},
    "The Daily Mirror": {"twitter": "@Mirror", "tags": "#News"},
    "Marca": {"twitter": "@marca", "tags": "#Deporte"},
    "AS": {"twitter": "@diarioas", "tags": "#Deporte"},
    "Gazzetta dello Sport": {"twitter": "@Gazzetta_it", "tags": "#Sport"},
    "L'Équipe": {"twitter": "@lequipe", "tags": "#Sport"},
}


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
        try:
            category = dom_dict["newsstand"]["name"]
        except KeyError:
            print(f"Issue getting data for {endpoint}")
        else:
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


def populate_db(items: list) -> list:
    """
    Populates the database with the given list of items.

    Args:
        items (list): A list of items to be inserted into the database.

    Returns:
        None
    """
    count = 0
    updated = 0
    new_capas = []
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
        dbitem = collection.find_one({"item_id": item["item_id"]})
        new_item = {
            "name": item["name"],
            "editions": [{"publish_date": item["publish_date"], "image_url": item["image_url"]}],
            "link": item["link"],
            "item_id": item["item_id"],
            "category": item["category"],
        }
        if not dbitem:
            collection.insert_one(new_item)
            new_capas.append(new_item)
            count += 1
        else:
            if item["publish_date"] == dbitem["editions"][0]["publish_date"]:
                if item["image_url"] != dbitem["editions"][0]["image_url"]:
                    collection.update_one(
                        {"item_id": item["item_id"]},
                        {
                            "$set": {
                                "editions.0": {"publish_date": item["publish_date"], "image_url": item["image_url"]}
                            }
                        },
                    )
                    new_capas.append(new_item)
                    updated += 1
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
                new_capas.append(new_item)
                count += 1

    # if count > 0 or updated > 0:
    #     requests.get(VERCEL_WEBHOOK)

    print(f"Inserted {count} capas and updated {updated} capas")
    return new_capas


def get_twitter_conn_v1() -> tweepy.API:
    """
    Return a Twitter connection using the OAuth1UserHandler authentication method.

    Returns:
        tweepy.API: A Twitter API object that can be used to interact with the Twitter API.

    """

    auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
    auth.set_access_token(
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_SECRET,
    )
    return tweepy.API(auth)


def get_twitter_conn_v2() -> tweepy.Client:
    """
    Create and return a Twitter connection using the provided API credentials.

    Return: An instance of the tweepy.Client class representing the Twitter connection.
    type: tweepy.Client
    """

    client = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
    )

    return client


def upload_media_twitter(file_name: str) -> int:
    """
    Uploads media from a given image URL to Twitter and returns the media ID.

    Args:
        image_url (str): The URL of the image to be uploaded.
        item_id (str): The ID of the item associated with the media.
        publish_date (str): The publish date of the item.

    Returns:
        int: The media ID of the uploaded image.
    """

    tweepy_api = get_twitter_conn_v1()
    print("Uploading media...")
    post = tweepy_api.media_upload(filename=file_name)
    media_id = post.media_id
    return media_id


def tweet_capa(name: str, publish_date: str, media_id: int):
    """
    Tweet the given information along with the media to the specified Twitter account.

    Args:
        name (str): The name of the Twitter account to tweet to.
        publish_date (str): The date of the tweet.
        media_id (int): The ID of the media to be attached to the tweet.

    Returns:
        None
    """

    client = get_twitter_conn_v2()
    try:
        print("Tweeting...")
        client.create_tweet(
            text=f" {name} {publish_date} {CAPAS[name]['twitter']} {CAPAS[name]['tags']}",
            media_ids=[media_id],
        )
    except TwitterServerError as e:
        print(e)


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
    new_capas = populate_db(capas)

    for capa in new_capas:
        if capa["name"] in CAPAS:
            file_name = f"{capa['item_id']}_{capa['editions'][0]['publish_date']}.jpg"
            img_data = requests.get(capa["editions"][0]["image_url"]).content
            with open(file_name, "wb") as handler:
                handler.write(img_data)
            media_id = upload_media_twitter(file_name)
            tweet_capa(capa["name"], capa["editions"][0]["publish_date"], media_id)
            print(f"Tweeted {capa['name']}")
            os.remove(file_name)


if __name__ == "__main__":
    main()
