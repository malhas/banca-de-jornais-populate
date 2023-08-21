import xmltodict
import os
import requests
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
import tweepy

load_dotenv()

MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")
BASE_URL = "https://services.sapo.pt/News/NewsStand/"
ENDPOINTS = ["National", "Sport", "Economy", "International", "Regional", "Magazine"]
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET")

TWITTER_ACCOUNTS = {
    "Expresso": {"account": "@expresso", "tags": "#Notícias"},
    "SOL": {"account": "@solonline", "tags": "#Notícias"},
    "Correio da Manhã": {"account": "@cmjornal", "tags": "#Notícias"},
    "Jornal de Notícias": {"account": "@jornalnoticias", "tags": "#Notícias"},
    "Público": {"account": "@publico", "tags": "#Notícias"},
    "Diário de Notícias": {"account": "@dntwit", "tags": "#Notícias"},
    "Diário Económico": {"account": "@diarioeconomico", "tags": "#Economia"},
    "Jornal de Negócios": {"account": "@JNegocios", "tags": "#Economia"},
    "O Jogo": {"account": "@ojogo", "tags": "#Deporto"},
    "A Bola": {"account": "@abolapt", "tags": "#Desporto"},
    "Record": {"account": "@Record_Portugal", "tags": "#Desporto"},
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
    collection = db["Capas"]
    for item in items:
        dbitem = collection.find_one(
            {"name": item["name"], "publish_date": item["publish_date"], "item_id": item["item_id"]}
        )
        if not dbitem:
            collection.insert_one(item)
            new_capas.append(item)
            count += 1
        else:
            if item["image_url"] != dbitem["image_url"]:
                collection.update_one(
                    {"name": item["name"], "publish_date": item["publish_date"], "item_id": item["item_id"]},
                    {"$set": item},
                )
                new_capas.append(item)
                updated += 1

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


def upload_media(image_url: str, item_id: str, publish_date: str) -> int:
    """
    Uploads media from a given image URL to Twitter and returns the media ID.

    Args:
        image_url (str): The URL of the image to be uploaded.
        item_id (str): The ID of the item associated with the media.
        publish_date (str): The publish date of the item.

    Returns:
        int: The media ID of the uploaded image.
    """

    file_name = f"{item_id}_{publish_date}.jpg"
    tweepy_api = get_twitter_conn_v1()
    img_data = requests.get(image_url).content
    with open(file_name, "wb") as handler:
        handler.write(img_data)
    post = tweepy_api.media_upload(filename=file_name)
    media_id = post.media_id
    os.remove(file_name)
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
    client.create_tweet(
        text=f" {name} {publish_date} {TWITTER_ACCOUNTS[name]['account']} {TWITTER_ACCOUNTS[name]['tags']}",
        media_ids=[media_id],
    )


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
        if capa["name"] in TWITTER_ACCOUNTS:
            media_id = upload_media(
                capa["image_url"],
                capa["item_id"],
                capa["publish_date"],
            )
            tweet_capa(capa["name"], capa["publish_date"], media_id)
            print(f"Tweeted {capa['name']}")


if __name__ == "__main__":
    main()
