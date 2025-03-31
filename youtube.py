from sqlalchemy import create_engine
import geopandas as gpd
from sqlalchemy.sql import text
import os 
from openai import OpenAI
from pydantic import BaseModel, Field
import json 
from flask import jsonify

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def connect_to_db(db_user="justin", db_password="Jesus-2016", db_host="localhost", db_name="spatialbot_db"):
    engine = create_engine(f"postgresql://{db_user}:{db_password}@{db_host}/{db_name}")
    return engine

def get_layers_names():
    with connect_to_db().connect() as connection:
        statement = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name != 'spatial_ref_sys';")
        result = connection.execute(statement).fetchall()
        return [name[0] for name in result]
    

def get_layer_data_base_on_name(layer_name):
    query = f"SELECT * FROM {layer_name}"
    return gpd.read_postgis(query, connect_to_db())


# 1. Calculate intersection between layer
def get_intersection(layer1, layer2):
    """Return the intersection between two layers"""
    result = gpd.overlay(get_layer_data_base_on_name(layer1), get_layer_data_base_on_name(layer2), how='intersection')
    print("result : ", result)
    result.to_file(r"D:\vs_code_test\spatialbot_test\data.json", driver="GeoJSON")
   

def call_function(name, args):
    if name == "get_intersection":
        return get_intersection(**args)
    if name == "get_layers_names":
        return get_layers_names()
    
class IntersectionResponse(BaseModel):
    layer1: str = Field(
        description="Name of the first layer"
    )
    layer2: str = Field(
        description="Name of the second layer"
    )
    operation: str = Field(
        description="The name of the operation apply to the layers. Exemple this can be intersection, buffer etc. All operations relate to spatial interaction"
    )
    response : str = Field(
        description="A natural language response to the user's question. Example : I have complete the tasks. What do you want to do next ?"
    )

class LayerListResponse(BaseModel):
    layers: list[str] = Field(..., description="List of layer names from the database")
    response: str = Field(..., description="Natural language response explaining the layers. And ask to the user which layer he want to load")




if __name__=="__main__":
    print('Debut du programme')

    tools = [
        {
        "type": "function",
        "function": {
            "name": "get_intersection",
            "description": "Calcul the spatial intersection between 2 layers",
            "parameters": {
            "type": "object",
            "properties": {
                "layer1" : {"type" : "string", "description": "The first layer name"},
                "layer2" : {"type" : "string", "description": "The second layer name"}
            },
            "required": ["layer1", "layer2"], 
            "additionalProperties": False
            }, 
            "strict" : True
        }
        }, 
        {
        "type": "function",
        "function": {
            "name": "get_layers_names",
            "description": "Get the name of the layers in the database", 
            "parameters": {
            "type": "object",
            "properties": {},
            "required": [], 
            "additionalProperties": False
            }, 
            "strict" : True
        }
        }
    ]

    
    system_prompt = """
    Vous etes un assitant permettant d'effectuer des operations spatiales sur des couches de donnees geospatiales.
    Si l'utilisateur demande a consulter les couches dans la base de donnees, il faut utiliser la fonction get_layers_names.
    Si l'utilisateur demande a effectuer une operation spatiale entre deux couches, il faut utiliser la fonction get_intersection.
    Vous devez repondre a l'utilisateur en francais.
 
    """
    messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content" :"Quel est l'intersection spatiale entre la couche de donnees hydro et la couche de donnees emprise ?" }
    ]

    completion = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=messages,
        tools=tools
    )

    completion.model_dump()

    for tool_call in completion.choices[0].message.tool_calls:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        print(args)
        messages.append(completion.choices[0].message)

        result = call_function(name, args)
        messages.append({
            "role" : "tool", 
            "tool_call_id": tool_call.id, 
            "content": json.dumps(result)
        })

    completion_2 = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06", 
        messages=messages, 
        tools=tools,
        response_format=IntersectionResponse
    )

    final_response = completion_2.choices[0].message.parsed
    # print(final_response.layers)
    # print(final_response.response)

    print(final_response.layer1)
    print(final_response.layer2)
    print(final_response.operation)
    print(final_response.response)




   