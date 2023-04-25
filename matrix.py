import os
import io
import aiofiles.os
from PIL import Image
from nio import AsyncClient, UploadResponse
import base64


async def upload_image(client: AsyncClient, image: Image.Image) -> UploadResponse:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_data = buffer.getvalue()

    response, maybe_keys = await client.upload(
        io.BytesIO(image_data),
        content_type="image/png",
        filename="location.png",
        filesize=len(image_data),
    )

    return response


async def send_room_image(
    client: AsyncClient, room_id: str, upload_response: UploadResponse
):
    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={"msgtype": "m.image", "url": upload_response.content_uri, "body": ""},
    )


async def send_image(client: AsyncClient, room_id: str, image: Image.Image):
    response = await upload_image(client=client, image=image)
    await send_room_image(client, room_id, upload_response=response)
