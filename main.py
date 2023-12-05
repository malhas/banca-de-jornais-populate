import xmltodict
import os
import requests
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
import tweepy
from tweepy.errors import TwitterServerError
from instagrapi import Client
from PIL import Image

load_dotenv()

MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")
BASE_URL = "https://services.sapo.pt/News/NewsStand/"
ENDPOINTS = ["National", "Sport", "Economy", "International", "Regional", "Magazine"]
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET")
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD")
VERCEL_WEBHOOK = os.environ.get("VERCEL_WEBHOOK")

CAPAS = {
    "Expresso": {"twitter": "@expresso", "instagram": "@jornalexpresso", "tags": "#Notícias"},
    "Nascer do SOL": {"twitter": "@solonline", "instagram": "@jornalsol", "tags": "#Notícias"},
    "Correio da Manhã": {"twitter": "@cmjornal", "instagram": "@correiodamanhaoficial", "tags": "#Notícias"},
    "Jornal de Notícias": {"twitter": "@jornalnoticias", "instagram": "@jornaldenoticias", "tags": "#Notícias"},
    "Público": {"twitter": "@publico", "instagram": "@publico.pt", "tags": "#Notícias"},
    "Diário de Notícias": {"twitter": "@dntwit", "instagram": "@diariodenoticias.pt", "tags": "#Notícias"},
    "O Jornal Económico": {"twitter": "@ojeconomico", "instagram": "@jornaleconomico", "tags": "#Economia"},
    "Jornal de Negócios": {"twitter": "@JNegocios", "instagram": "@negocios.pt", "tags": "#Economia"},
    "O Jogo": {"twitter": "@ojogo", "instagram": "@diariodesportivo.ojogo", "tags": "#Desporto"},
    "A Bola": {"twitter": "@abolapt", "instagram": "@abolapt", "tags": "#Desporto"},
    "Record": {"twitter": "@Record_Portugal", "instagram": "@record_portugal", "tags": "#Desporto"},
    "El País": {"twitter": "@elpais_espana", "instagram": "@el_pais", "tags": "#Noticias"},
    "El Mundo": {"twitter": "@elmundoes", "instagram": "@elmundo_es", "tags": "#Noticias"},
    "Le Monde": {"twitter": "@lemondefr", "instagram": "@lemondefr", "tags": "#Noticias"},
    "Le Figaro": {"twitter": "@Le_Figaro", "instagram": "@lefigarofr", "tags": "#Noticias"},
    "The Daily Telegraph": {"twitter": "@Telegraph", "instagram": "@telegraph", "tags": "#News"},
    "The Guardian": {"twitter": "@guardian", "instagram": "@guardian", "tags": "#News"},
    "The Independent": {"twitter": "@independent", "instagram": "@the.independent", "tags": "#News"},
    "The Daily Mirror": {"twitter": "@Mirror", "instagram": "@dailymirror", "tags": "#News"},
    "Marca": {"twitter": "@marca", "instagram": "@marca", "tags": "#Deporte"},
    "AS": {"twitter": "@diarioas", "instagram": "@diarioas", "tags": "#Deporte"},
    "Gazzetta dello Sport": {"twitter": "@Gazzetta_it", "instagram": "@gazzettadellosport", "tags": "#Sport"},
    "L'Équipe": {"twitter": "@lequipe", "instagram": "@lequipe", "tags": "#Sport"},
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


def get_insta_conn() -> Client:
    """
    Get an instance of the `Client` class to connect to Instagram.

    :return: An instance of the `Client` class.
    :rtype: Client
    """
    cl = Client()
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

    return cl


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


def post_insta(cl: Client, file_name: str, name: str, publish_date: str):
    """
    Posts the given information to the specified Instagram account.

    Args:
        image_url (str): The URL of the image to be posted.
        item_id (str): The ID of the item associated with the media.
        publish_date (str): The publish date of the item.

    Returns:
        None
    """

    insta_file_name = "insta.jpg"

    image = Image.open(file_name).convert("RGB")
    new_image = image.resize((680, 1050))
    new_image.save(insta_file_name)
    cl.photo_upload(
        insta_file_name,
        caption=f"{name} {publish_date} {CAPAS[name]['instagram']} {CAPAS[name]['tags']}",
    )
    os.remove(insta_file_name)


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

    # cl = get_insta_conn()
    for capa in new_capas:
        if capa["name"] in CAPAS:
            file_name = f"{capa['item_id']}_{capa['publish_date']}.jpg"
            img_data = requests.get(capa["image_url"]).content
            with open(file_name, "wb") as handler:
                handler.write(img_data)
            media_id = upload_media_twitter(file_name)
            tweet_capa(capa["name"], capa["publish_date"], media_id)
            print(f"Tweeted {capa['name']}")
            # post_insta(cl, file_name, capa["name"], capa["publish_date"])
            # print(f"Posted {capa['name']}")
            os.remove(file_name)
    # cl.logout()


if __name__ == "__main__":
    main()
