import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

FACTS = [
    # Animals
    "Octopuses have three hearts and blue blood.",
    "A group of flamingos is called a flamboyance.",
    "Wombats produce cube-shaped poop.",
    "A snail can sleep for up to three years.",
    "Sharks are older than trees — they've existed for over 450 million years.",
    "A group of crows is called a murder.",
    "Cows have best friends and get stressed when separated from them.",
    "Mantis shrimp can punch with the force of a bullet and see 16 types of color receptors (humans have 3).",
    "Sloths can hold their breath longer than dolphins — up to 40 minutes.",
    "Crows are so intelligent they hold grudges and pass them down to their offspring.",
    "A group of owls is called a parliament.",
    "Butterflies taste with their feet.",
    "A shrimp's heart is in its head.",
    "Elephants are the only animals that can't jump.",
    "Sea otters hold hands while sleeping so they don't drift apart.",
    "A crocodile can't stick its tongue out.",
    "Polar bears have black skin under their white fur.",
    "Dolphins give each other names and respond when called.",
    "The axolotl can regrow its heart, brain, and limbs.",
    "Tardigrades can survive in the vacuum of space.",

    # History & People
    "Cleopatra lived closer in time to the Moon landing than to the construction of the Great Pyramid.",
    "The shortest war in history lasted 38-45 minutes — Britain vs. Zanzibar in 1896.",
    "Oxford University is older than the Aztec Empire.",
    "Nintendo was founded in 1889 as a playing card company.",
    "The inventor of the Pringles can, Fredric Baur, had his ashes buried in one.",
    "Napoleon was once attacked by rabbits.",
    "Ancient Romans used crushed mouse brains as toothpaste.",
    "The Great Wall of China is not visible from space with the naked eye — astronauts confirmed this.",
    "Vikings used to give kittens to new brides as essential household gifts.",
    "Abraham Lincoln was a licensed bartender.",
    "The fax machine was invented before the telephone.",
    "The first computer bug was an actual bug — a moth found in a Harvard relay in 1947.",
    "Einstein failed his first university entrance exam.",
    "Michelangelo was 72 years old when he designed the dome of St. Peter's Basilica.",
    "Charles Darwin and Abraham Lincoln were born on the exact same day.",
    "King Henry VIII owned a pair of spectacles for his pet monkey.",
    "Salvador Dali claimed he used to take micro-naps with a key in his hand to capture hypnagogic images.",
    "Marie Curie's notebooks are still so radioactive they're kept in lead-lined boxes.",
    "Beethoven composed some of his greatest works after going completely deaf.",

    # Science & Nature
    "Honey never spoils — 3,000-year-old honey found in Egyptian tombs was still edible.",
    "Bananas are technically berries, but strawberries are not.",
    "The Eiffel Tower can be 15 cm taller in summer due to thermal expansion.",
    "There are more possible chess game iterations than atoms in the observable universe.",
    "The human nose can detect over 1 trillion different scents.",
    "A day on Venus is longer than a year on Venus.",
    "Water can boil and freeze simultaneously — it's called the triple point.",
    "The human body contains enough iron to make a 3-inch nail.",
    "Hot water freezes faster than cold water under certain conditions — the Mpemba effect.",
    "Lightning strikes the Earth about 100 times per second.",
    "A teaspoon of neutron star material would weigh about 10 million tons.",
    "There are more trees on Earth than stars in the Milky Way.",
    "Humans share 60% of their DNA with bananas.",
    "The Sun makes up 99.86% of the total mass of our solar system.",
    "There are more possible ways to shuffle a deck of cards than there are atoms on Earth.",
    "A bolt of lightning is five times hotter than the surface of the Sun.",
    "Stomach acid is strong enough to dissolve razor blades.",
    "The human eye can detect a single photon of light in total darkness.",
    "Identical twins don't have the same fingerprints.",
    "The average cloud weighs about 1.1 million pounds.",

    # Language & Words
    "The dot over the letters 'i' and 'j' is called a tittle.",
    "The word 'nerd' was first coined by Dr. Seuss in 'If I Ran the Zoo' (1950).",
    "The word 'muscle' comes from Latin for 'little mouse' — flexing muscles were thought to look like mice moving under skin.",
    "'Dreamt' is the only common English word that ends in 'mt'.",
    "The word 'set' has the most definitions of any word in English.",
    "The @ symbol is called an 'arroba' in Spanish and Portuguese.",
    "The word 'salary' comes from the Latin word for salt — Roman soldiers were sometimes paid in salt.",
    "The word 'robot' was first used in a 1920 Czech play.",
    "The ampersand (&) was once the 27th letter of the English alphabet.",
    "The word 'quiz' is said to have been invented in 1791 as a bet to put a new word into common usage overnight.",

    # Food & Drink
    "Carrots were originally purple — the orange variety was bred by the Dutch in the 17th century.",
    "Ketchup was sold as medicine in the 1830s.",
    "Peanuts are not nuts — they're legumes, more closely related to beans.",
    "Apples, pears, and plums are members of the rose family.",
    "Avocados are technically a single-seeded berry.",
    "Nutmeg can be toxic in large amounts — just a few teaspoons can cause hallucinations.",
    "Cashews grow on the bottom of a fruit called the cashew apple.",
    "Chocolate milk was invented in Jamaica in the late 1600s.",
    "Pistachios are technically fruits, not nuts.",
    "The world's most expensive spice by weight is saffron — it takes about 75,000 flowers to produce one pound.",

    # Space & Earth
    "There are more atoms in a glass of water than glasses of water in all the world's oceans.",
    "If you removed all the empty space in atoms, all of humanity would fit in a sugar cube.",
    "The Voyager 1 spacecraft, launched in 1977, has left our solar system.",
    "One million Earths could fit inside the Sun.",
    "The footprints on the Moon will last for millions of years — there's no wind to erode them.",
    "Saturn's rings are only about 30 feet thick on average despite being 175,000 miles wide.",
    "Mercury and Venus are the only planets in our solar system with no moons.",
    "It takes a photon 100,000 years to travel from the Sun's core to its surface, then 8 minutes to reach Earth.",
    "There's a giant cloud of alcohol in space — the Sagittarius B2 cloud contains enough ethyl alcohol to fill 400 trillion trillion pints.",

    # Miscellaneous
    "There are more fake flamingos in the world than real ones.",
    "The plastic tips on shoelaces are called aglets.",
    "The average person walks about 100,000 miles in their lifetime — roughly four trips around the Earth.",
    "The world's oldest known recipe is for beer, from ancient Sumeria circa 1800 BC.",
    "LEGO is the world's largest tire manufacturer by number of tires produced annually.",
    "More people have been to space than have reached the deepest point of the ocean.",
    "The inventor of the World Wide Web, Tim Berners-Lee, never patented it.",
    "A standard Rubik's Cube has 43 quintillion possible configurations.",
    "The shortest commercially scheduled flight in the world takes under 2 minutes.",
    "A jiffy is an actual unit of time — 1/100th of a second.",
]


async def seed():
    uri = os.getenv("mongo_db_string")
    if not uri:
        print("ERROR: mongo_db_string env var not set.")
        return
    client = AsyncIOMotorClient(uri)
    db = client["triviabot"]
    col = db["fun_facts"]
    count = await col.count_documents({})
    if count > 0:
        print(f"Collection already has {count} facts. Skipping seed.")
        client.close()
        return
    result = await col.insert_many([{"text": f} for f in FACTS])
    print(f"Inserted {len(result.inserted_ids)} facts into fun_facts.")
    client.close()


asyncio.run(seed())
