from mongo_db_handler import MongoDBHandler


mongo_db_handler = MongoDBHandler(
    "mongodb+srv://smartGh-00:Smartgreenhouse1@greenhouse.ibf6l7y.mongodb.net/?retryWrites=true&w=majority&appName=GreenHouse", "GreenHouse")


listed = mongo_db_handler.get_latest_doc_where("setpoints", {"type": "temperature"})
print(listed)