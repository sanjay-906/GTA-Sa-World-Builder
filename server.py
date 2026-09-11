import json
import socket

from fastmcp import FastMCP

from assets import get_asset, list_assets, search_assets

HOST = "127.0.0.1"
PORT = 8765


mcp = FastMCP("GTA San Andreas Map Editor")


def gta_call(command, params=None):

    request = {
        "command": command,
        "params": params or {},
    }

    with socket.create_connection(
        (HOST, PORT),
        timeout=5,
    ) as sock:

        sock.sendall(
            (
                json.dumps(request) + "\n"
            ).encode("utf-8")
        )

        file = sock.makefile(
            "r",
            encoding="utf-8",
        )

        line = file.readline()

        if not line:
            raise RuntimeError(
                "GTA bridge closed the connection"
            )

        return json.loads(line)


@mcp.tool()
def gta_status() -> dict:
    """
    Check whether GTA San Andreas and
    the PyAndreas bridge are running.
    """

    return gta_call("status")


@mcp.tool()
def gta_get_player_position() -> dict:
    """
    Get CJ's current world position and heading.
    """

    return gta_call(
        "get_player_position"
    )


@mcp.tool()
def gta_get_position_in_front(distance: float = 3.0) -> dict:
    """
    Calculate a ground-level position in front of CJ.

    distance:
        Distance from CJ in GTA world units.
    """

    return gta_call(
        "get_position_in_front",
        {
            "distance": distance,
        },
    )


@mcp.tool()
def gta_add_object(model_id: int, x: float, y: float, z: float) -> dict:
    """
    Spawn a GTA object at an exact world position.

    model_id:
        Numeric GTA object model ID.

    x, y, z:
        GTA world coordinates.
    """

    return gta_call(
        "add_object",
        {
            "model_id": model_id,
            "x": x,
            "y": y,
            "z": z,
        },
    )


@mcp.tool()
def gta_add_object_in_front(model_id: int, distance: float = 3.0) -> dict:
    """
    Spawn a GTA object on the ground in front of CJ.
    """

    return gta_call(
        "add_object_in_front",
        {
            "model_id": model_id,
            "distance": distance,
        },
    )


@mcp.tool()
def gta_list_assets() -> dict:
    """
    List all registered GTA assets.

    Each asset has a human-friendly name and GTA model ID.
    """

    return {
        "ok": True,
        "assets": list_assets(),
    }


@mcp.tool()
def gta_search_assets(query: str) -> dict:
    """
    Search the GTA asset registry.

    Examples:
        tree
        palm
        lamp
        street
        dead
    """

    return {
        "ok": True,
        "query": query,
        "results": search_assets(query),
    }


@mcp.tool()
def gta_get_asset(asset: str) -> dict:
    """
    Get information about a named GTA asset.
    """

    definition = get_asset(asset)

    if definition is None:

        return {
            "ok": False,
            "error": f"Unknown asset: {asset}",
            "available_assets": list_assets(),
        }

    return {
        "ok": True,
        "asset": asset,
        "definition": definition,
    }


@mcp.tool()
def gta_spawn_asset_in_front(asset: str, distance: float = 3.0) -> dict:
    """
    Spawn a named GTA asset on the ground in front of CJ.

    Example:

        asset="tree_hipoly07"
        distance=5
    """

    definition = get_asset(asset)

    if definition is None:

        return {
            "ok": False,
            "error": f"Unknown asset: {asset}",
            "available_assets": list_assets(),
        }

    return gta_call(
        "add_object_in_front",
        {
            "model_id": definition["model_id"],
            "distance": distance,
        },
    )


@mcp.tool()
def gta_spawn_named_object_in_front(object_name: str, distance: float = 3.0) -> dict:
    """
    Spawn a GTA object using its GTA object name.

    Example:
        object_name="tree_hipoly07"
    """

    return gta_call(
        "add_named_object_in_front",
        {
            "object_name": object_name,
            "distance": distance,
        },
    )


@mcp.tool()
def gta_get_nearby_objects(radius: float = 20.0) -> dict:
    """
    Get GTA objects near CJ.
    """

    return gta_call(
        "get_nearby_objects",
        {
            "radius": radius,
        },
    )


@mcp.tool()
def gta_remove_object(object_id: str) -> dict:
    """
    Remove an object previously created
    by the GTA MCP bridge.
    """

    return gta_call(
        "remove_object",
        {
            "object_id": object_id,
        },
    )


@mcp.tool()
def gta_undo() -> dict:
    """
    Undo the most recent supported GTA map edit.
    """

    return gta_call("undo")


if __name__ == "__main__":
    mcp.run(show_banner=False)
