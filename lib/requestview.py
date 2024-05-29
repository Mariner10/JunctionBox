import json
import lib.ntfy
import os
from dotenv import load_dotenv
load_dotenv()


def drawRequestView():

    try:

        with open("JSON/requests.json", "r") as requests_file:
            requestDict = json.load(requests_file)

        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Request Logs</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }}
                .button-container {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    margin-bottom: 20px;
                }}
                .button {{
                    background-color: #395d85;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                }}
                .button:hover {{
                    background-color: #0056b3;
                }}
                .details {{
                    display: none;
                    margin: 10px 0 20px 0;
                    padding: 15px;
                    border: 1px solid #ddd;
                    border-radius: 10px;
                    background-color: #f9f9f9;
                }}
                .details ul {{
                    list-style-type: none;
                    padding: 0;
                }}
                .details li {{
                    margin: 5px 0;
                }}
            </style>
            <script>
                function toggleDetails(id) {{
                    var element = document.getElementById(id);
                    if (element.style.display === "none") {{
                        element.style.display = "block";
                    }} else {{
                        element.style.display = "none";
                    }}
                }}
            </script>
        </head>
        <body>
            <h1>Request Logs</h1>
            <div class="button-container">
                {content}
            </div>
        </body>
        </html>
        """

        content = ""
        for ip, details in requestDict.items():
            content += f'<button class="button" onclick="toggleDetails(\'{ip}\')">{ip}</button>'
            details_html = "<ul>"
            for key, value in details.items():
                details_html += f"<li><strong>{key}:</strong> {value}</li>"
            details_html += "</ul>"
            content += f'<div id="{ip}" class="details">{details_html}</div>'

        html_output = html_template.format(content=content)

        with open("HTML/requests.html", "w") as output_file:
            output_file.write(html_output)

        return True
    except Exception as e:
        ntfy.send("DEBUG ERROR!", f"Exception: {e}", os.getenv("NTFY_ALERTS"))
        return False