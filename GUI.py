import os
import sys
from django.conf import settings
from django.core.management import execute_from_command_line
from django.urls import path
from django.http import HttpResponse
from django.template import Engine
from django.template import Context

# Correctly configure the Django settings
settings.configure(
    DEBUG=True,
    ROOT_URLCONF=__name__,
    SECRET_KEY='not_so_secret',
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
        },
    ],
)


def command_runner(request):
    template = Engine.get_default().from_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Command Runner</title>
            <style>
                body, html { margin: 0; padding: 0; width: 100%; height: 100%; }
                .bg { 
                    position: fixed; 
                    top: 0; left: 0; 
                    width: 100%; height: 100%;
                    background: url('https://telecomtalk.info/wp-content/uploads/2023/12/ntt-gdcj-tepco-to-develop-datacenters-japan.jpg') no-repeat center center fixed; 
                    background-size: cover;
                    filter: blur(8px); 
                    -webkit-filter: blur(8px);
                    z-index: -1;
                }
                .container { 
                    display: flex; flex-direction: column; height: 100vh; position: relative; 
                }
                .horizontal { display: flex; height: 50%; }
                .section { flex: 1; padding: 10px; box-sizing: border-box; color: white; }
                #section1a, #section1b { 
                    display: flex; 
                    justify-content: center; 
                    align-items: center; 
                    font-size: 20px;

                }
                textarea { 
                    width: 100%; 
                    padding: 10px; 
                    margin: 10px 0;
                    box-sizing: border-box;
                    color: black;
                    resize: none; 
                }
                .drop-area { 
                    height: 50%;
                    background-color: #f0f0f0; 
                    color: grey;
                    padding: 10px; 
                    box-sizing: border-box; 
                    position: relative;
                }
                .draggable { 
                    cursor: pointer; 
                    user-select: none; 
                    padding: 20px; 
                    font-size: 18px; 
                    margin: 5px; 
                    background-color: lightgrey; 
                    border: none; 
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
        <div class="bg"></div>
        <div class="container">
            <div id="section1" class="horizontal">

            <div id="section2" class="section" style="background-color: rgba(255,255,255,0.5);">
                <textarea placeholder="Enter device details..."></textarea>
                <button id="button0" class="draggable" draggable="false">Run commands</button>
                <div class="drop-area" ondrop="drop(event)" ondragover="allowDrop(event)" placeholder="drop your commands here" style="background-color: rgba(255,255,255,0.5);">drop your commands here</div>
            </div>
            <div id="section3" class="section" style="background-color: rgba(255,255,255,0.5);">
                <button id="button1" class="draggable" draggable="true" ondragstart="drag(event)">Show clock</button>
                <button id="button2" class="draggable" draggable="true" ondragstart="drag(event)">Show wireless client Summary</button>
                <button id="button3" class="draggable" draggable="true" ondragstart="drag(event)">Show ap Summary</button>
            </div>

        </div>

        <script>
            function allowDrop(ev) {
                ev.preventDefault();
            }

            function drag(ev) {
                ev.dataTransfer.setData("text", ev.target.id);
            }

            function drop(ev) {
                ev.preventDefault();
                var data = ev.dataTransfer.getData("text");
                var nodeCopy = document.getElementById(data).cloneNode(true);
                nodeCopy.id = "newId"; // Generate a unique ID or handle duplicates as needed
                nodeCopy.onclick = function() { this.remove(); }; // Remove button on click
                ev.target.appendChild(nodeCopy);
            }
        </script>

        </body>
        </html>
    ''')
    return HttpResponse(template.render(Context({})))


def index(request):
    template = Engine.get_default().from_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Client Dropdown</title>
        <style>
            .dropdown {
                position: absolute;
                top: 49%;
                left: 49.3%;
                transform: translate(-50%, -50%);
                width: 500px; /* Recommended width */
            }

            .dropdown select:hover {
                background-color: #f0f0f0; /* Highlight color on hover */
            }

            select {
                width: 110%;
                height: 95px;
                font-size: 40px;
                padding: 10px 20px;

            }
            body {
                background: url('https://telecomtalk.info/wp-content/uploads/2023/12/ntt-gdcj-tepco-to-develop-datacenters-japan.jpg') no-repeat center center fixed; 
                background-size: cover;

            }

            .fyi-text {
                position: absolute;
                width: 550px;
                top: 52%; /* Example position */
                left: 40.5%; /* Example position */
                background-color: rgba(255,255,255,0.5); /* Semi-transparent background */
                padding: 20px;
                font-size: 27px;
            }
        </style>
    </head>
    <body>

    <div class="dropdown">
        <select name="clients" id="clients" onchange="changeClient(this.value)">
            <option value="" disabled selected>Select a client...</option>
            <option value="/Command_runner/">DS Smith</option>
            <option value="/Command_runner/">Suncorp</option>
        </select>
    </div>

    <div class="fyi-text">
        NOTE: Users will only have visibility of the clients they are authorized to access.






.
    </div>

    <script>
        function changeClient(value) {
            if (value) {
                window.location.href = value;
            }
        }
    </script>

    </body>
    </html>
    """)
    return HttpResponse(template.render(Context({})))


# URL Configuration
urlpatterns = [
    path('', index),
    path('Command_runner/', command_runner),
]

if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '__main__')
    execute_from_command_line(sys.argv)