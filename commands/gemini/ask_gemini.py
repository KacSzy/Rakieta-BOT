import os
import requests
import discord

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

async def handle_gemini_command(interaction: discord.Interaction, question: str):
    if not question:
        await interaction.followup.send("Proszę podać pytanie.")
        return

    # Call Gemini API
    try:
        gemini_response = _call_gemini_api(question + '(max 1500 znakow)')

        # Format the complete response with question and answer
        complete_response = f"**Pytanie:**\n {question}\n\n**Odpowiedź:**\n {gemini_response}"

        # Discord's character limit
        if len(complete_response) <= 2000:
            await interaction.followup.send(complete_response)
        else:
            await interaction.followup.send("Odpowiedź jest zbyt długa, aby ją wyświetlić.")

    except Exception as e:
        await interaction.followup.send(f"Error: {str(e)}")


def _call_gemini_api(prompt):
    """
    Call the Gemini API with the provided prompt
    """

    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    response = requests.post(
        GEMINI_API_URL,
        headers=headers,
        json=data
    )

    if response.status_code == 200:
        result = response.json()
        # Extract the text from the response
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return "Received an unexpected response format from Gemini API."
    else:
        return f"Error: {response.status_code} - {response.text}"
