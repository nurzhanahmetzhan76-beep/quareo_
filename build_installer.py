import os
import zipfile
import base64
import io

def build():
    ext_dir = "chrome_extension"
    if not os.path.exists(ext_dir):
        print("Папка chrome_extension не найдена!")
        return

    print("Создаю архив расширения...")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(ext_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, ext_dir)
                zip_file.write(file_path, arcname)

    b64_data = base64.b64encode(zip_buffer.getvalue()).decode("utf-8")

    installer_code = f"""import os
import sys
import base64
import zipfile
import io
import webbrowser

B64_ZIP = "{b64_data}"

HTML_TEMPLATE = \"\"\"<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Установка Автоответчика Quareo</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #F8FAFC; margin: 0; padding: 40px; color: #1E293B; }}
        .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); padding: 40px; }}
        h1 {{ color: #2563EB; font-size: 28px; margin-top: 0; display: flex; align-items: center; gap: 12px; }}
        .step {{ background: #F1F5F9; border-left: 4px solid #3B82F6; padding: 20px; border-radius: 0 12px 12px 0; margin-bottom: 24px; }}
        .step-title {{ font-weight: 700; font-size: 18px; margin-bottom: 10px; color: #0F172A; }}
        .copy-box {{ display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap; }}
        .path-input {{ flex: 1; min-width: 200px; padding: 12px 16px; border: 1px solid #CBD5E1; border-radius: 8px; font-family: monospace; font-size: 14px; background: #fff; color: #475569; outline: none; }}
        .btn {{ background: #2563EB; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.2s; white-space: nowrap; }}
        .btn:hover {{ background: #1D4ED8; }}
        .btn-success {{ background: #10B981 !important; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Файлы успешно распакованы!</h1>
        <p style="font-size: 16px; color: #475569; margin-bottom: 30px;">
            Осталось всего 3 простых шага, чтобы добавить Автоответчик в ваш браузер. Мы подготовили подробную инструкцию.
        </p>

        <div class="step">
            <div class="step-title">Шаг 1: Скопируйте путь к папке</div>
            <p style="margin: 0; color: #64748B;">Мы уже сохранили файлы расширения на вашем компьютере. Нажмите кнопку ниже, чтобы скопировать путь:</p>
            <div class="copy-box">
                <input type="text" class="path-input" id="pathInput" value="TARGET_DIR_PLACEHOLDER" readonly>
                <button class="btn" id="copyPathBtn" onclick="copyPath()">Скопировать путь</button>
            </div>
        </div>

        <div class="step">
            <div class="step-title">Шаг 2: Откройте страницу расширений Chrome</div>
            <p style="margin: 0; color: #64748B; margin-bottom: 15px;">Браузеры блокируют прямые ссылки для вашей безопасности, поэтому скопируйте этот адрес и вставьте его <b>в новую вкладку</b>:</p>
            <div class="copy-box">
                <input type="text" class="path-input" id="urlInput" value="chrome://extensions/" readonly>
                <button class="btn" id="copyUrlBtn" onclick="copyUrl()">Скопировать ссылку</button>
            </div>
        </div>

        <div class="step">
            <div class="step-title">Шаг 3: Включите Режим Разработчика</div>
            <p style="margin: 0; color: #64748B;">На открывшейся странице расширений, в правом верхнем углу включите тумблер <b>«Режим разработчика»</b> (Developer mode).</p>
        </div>

        <div class="step">
            <div class="step-title">Шаг 4: Загрузите расширение</div>
            <p style="margin: 0; color: #64748B;">
                Слева сверху появится кнопка <b>«Загрузить распакованное расширение»</b> (Load unpacked). Нажмите её, затем <b>вставьте скопированный путь</b> (Ctrl+V) в строку системного окна и нажмите "Выбор папки" (или Enter)!
            </p>
        </div>

        <div class="step" style="border-left-color: #10B981; background: #ECFDF5;">
            <div class="step-title">Шаг 5: Активируйте токен 🔑</div>
            <p style="margin: 0; color: #065F46;">
                Расширение установлено! Теперь вернитесь на сайт в <b>Личный кабинет</b>, скопируйте свой <b>"Токен авторизации"</b> и вставьте его в настройки расширения (нажмите на иконку 🧩 в браузере и выберите Quareo).
            </p>
        </div>
    </div>

    <script>
        function copyPath() {{
            var copyText = document.getElementById("pathInput");
            copyText.select();
            document.execCommand("copy");
            var btn = document.getElementById("copyPathBtn");
            btn.innerHTML = "✓ Скопировано!";
            btn.classList.add("btn-success");
            setTimeout(() => {{ btn.innerHTML = "Скопировать путь"; btn.classList.remove("btn-success"); }}, 3000);
        }}
        function copyUrl() {{
            var copyText = document.getElementById("urlInput");
            copyText.select();
            document.execCommand("copy");
            var btn = document.getElementById("copyUrlBtn");
            btn.innerHTML = "✓ Скопировано!";
            btn.classList.add("btn-success");
            setTimeout(() => {{ btn.innerHTML = "Скопировать ссылку"; btn.classList.remove("btn-success"); }}, 3000);
        }}
        
        window.onload = function() {{
            copyPath();
        }};
    </script>
</body>
</html>\"\"\"

def main():
    appdata = os.getenv("LOCALAPPDATA")
    target_dir = os.path.join(appdata, "QuareoExtension")
    
    try:
        os.makedirs(target_dir, exist_ok=True)
        zip_data = base64.b64decode(B64_ZIP)
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            zf.extractall(target_dir)
            
        # Сохраняем красивую инструкцию
        instruction_path = os.path.join(target_dir, "instruction.html")
        html_content = HTML_TEMPLATE.replace("TARGET_DIR_PLACEHOLDER", target_dir)
        with open(instruction_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        # Копируем путь в буфер обмена на всякий случай
        os.system(f"echo {{target_dir}}| clip")
        
        # Открываем инструкцию в браузере (она сама всё объяснит)
        webbrowser.open("file:///" + instruction_path.replace("\\\\", "/"))
        
    except Exception as e:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Произошла ошибка: {{str(e)}}", "Ошибка", 0x10 | 0x0)

if __name__ == "__main__":
    main()
"""

    with open("quareo_installer.py", "w", encoding="utf-8") as f:
        f.write(installer_code)
    
    print("--------------------------------------------------")
    print("Файл quareo_installer.py успешно сгенерирован!")
    print("Теперь выполните следующую команду в терминале, чтобы скомпилировать его в .exe:")
    print("pip install pyinstaller && pyinstaller --onefile --noconsole --name quareo_v2 --icon=chrome_extension/icons/icon48.png quareo_installer.py")
    print("Ваш готовый инсталлятор появится в папке dist/")

if __name__ == "__main__":
    build()
