import json
import socket
import threading
import traceback
import math

import pysa
from pysa import player, world
from gta_objects import GTA_OBJECTS


HOST = "127.0.0.1"
PORT = 8765


objects = {}
history = []


def response(ok=True, **data):
    return {"ok": ok, **data}


def send_response(conn, data):
    message = json.dumps(data) + "\n"
    conn.sendall(message.encode("utf-8"))


def get_player_position():
    pos = player.pos
    return {
        "x": float(pos.x),
        "y": float(pos.y),
        "z": float(pos.z),
    }


def get_position_in_front(distance=3.0):
    heading = math.radians(player.ped.heading)
    forward_x = -math.sin(heading)
    forward_y = math.cos(heading)

    x = player.pos.x + forward_x * distance
    y = player.pos.y + forward_y * distance
    z = world.ground_z(x, y)

    return {
        "x": float(x),
        "y": float(y),
        "z": float(z),
    }


def get_object_model_id(object_name):
    if object_name in GTA_OBJECTS:
        return GTA_OBJECTS[object_name]

    wanted = object_name.lower()

    for name, model_id in GTA_OBJECTS.items():
        if name.lower() == wanted:
            return model_id

    return None


def handle_request(request):
    command = request.get("command")
    params = request.get("params", {})

    if command == "status":

        return response(
            game="GTA San Andreas",
            bridge="PyAndreas",
            connected=True,
        )

    if command == "get_player_position":

        return response(
            position=get_player_position(),
            heading=float(player.ped.heading),
        )

    if command == "get_position_in_front":
        distance = float(params.get("distance", 3.0))
        position = get_position_in_front(distance)

        return response(
            position=position,
            distance=distance,
        )

    if command == "get_nearby_objects":
        radius = float(params.get("radius", 20.0))
        result = []
        for obj in world.objects.near(player.pos, radius):
            result.append(
                {
                    "id": str(id(obj)),
                    "model": int(obj.model),
                    "x": float(obj.pos.x),
                    "y": float(obj.pos.y),
                    "z": float(obj.pos.z),
                }
            )
        return response(
            objects=result,
        )

    if command == "add_object":
        model_id = int(params["model_id"])
        pos = (float(params["x"]), float(params["y"]), float(params["z"]))
        obj = pysa.GameObject.spawn(model_id, pos)
        object_id = str(id(obj))
        objects[object_id] = obj
        history.append(
            {
                "action": "add",
                "object_id": object_id,
            }
        )

        return response(
            object_id=object_id,
            model_id=model_id,
            position={
                "x": pos[0],
                "y": pos[1],
                "z": pos[2],
            },
        )

    if command == "add_object_in_front":
        model_id = int(params["model_id"])
        distance = float(params.get("distance", 3.0))
        position = get_position_in_front(distance)
        obj = pysa.GameObject.spawn(
            model_id,
            (
                position["x"],
                position["y"],
                position["z"],
            ),
        )
        object_id = str(id(obj))
        objects[object_id] = obj
        history.append(
            {
                "action": "add",
                "object_id": object_id,
            }
        )

        return response(
            object_id=object_id,
            model_id=model_id,
            position=position,
            distance=distance,
        )

    if command == "remove_object":
        object_id = params["object_id"]
        obj = objects.get(object_id)
        if obj is None:
            return response(
                False,
                error="Object not found",
            )
        obj.delete()
        del objects[object_id]
        history.append(
            {
                "action": "remove",
                "object_id": object_id,
            }
        )
        return response(
            removed=True,
            object_id=object_id,
        )

    if command == "undo":
        if not history:
            return response(
                False,
                error="Nothing to undo",
            )
        operation = history.pop()
        if operation["action"] == "add":
            object_id = operation["object_id"]
            obj = objects.get(object_id)
            if obj:
                obj.delete()
                del objects[object_id]

            return response(
                undone=True,
                action="add",
                object_id=object_id,
            )

        return response(
            False,
            error="Unsupported undo operation",
        )

    if command == "add_named_object_in_front":
        object_name = params["object_name"]
        distance = float(params.get("distance", 3.0))
        model_id = get_object_model_id(object_name)
        if model_id is None:
            return response(
                False,
                error=f"Unknown GTA object: {object_name}",
            )

        position = get_position_in_front(distance)
        obj = pysa.GameObject.spawn(
            model_id,
            (
                position["x"],
                position["y"],
                position["z"],
            ),
        )
        object_id = str(id(obj))
        objects[object_id] = obj
        history.append(
            {
                "action": "add",
                "object_id": object_id,
            }
        )

        return response(
            object_id=object_id,
            object_name=object_name,
            model_id=model_id,
            position=position,
            distance=distance,
        )

    return response(
        False,
        error=f"Unknown command: {command}",
    )


def client_thread(conn):
    try:
        file = conn.makefile("r", encoding="utf-8")
        for line in file:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                result = handle_request(request)
                send_response(conn, result)

            except Exception as exc:
                traceback.print_exc()
                send_response(
                    conn,
                    response(
                        False,
                        error=str(exc),
                    ),
                )

    finally:
        conn.close()


def server_thread():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[GTA-MCP] Listening on {HOST}:{PORT}")

    while True:
        conn, address = server.accept()
        print(f"[GTA-MCP] Connection from {address}")

        threading.Thread(target=client_thread, args=(conn,), daemon=True).start()


threading.Thread(target=server_thread, daemon=True).start()
