import csv
import os

def generate_csv():
    # Use standard python csv module to create a file for Excel
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Себестоимость_Quareo.csv")
    
    # Use utf-8-sig so Excel recognizes Cyrillic correctly
    with open(desktop_path, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Kaspi_ID', 'Название_товара', 'Себестоимость_KZT'])
        
        # Example for their store
        writer.writerow(['102345678', 'Смартфон Apple iPhone 15 Pro 256Gb (NurzhanAhmetzhan76)', '490000'])
        writer.writerow(['109876543', 'Защитное стекло iPhone 15 Pro', '1200'])
        writer.writerow(['105554433', 'Чехол силиконовый прозрачный', '500'])
        writer.writerow(['104889221', 'Зарядное устройство 20W Type-C', '3500'])
        
    print(f"Template created at {desktop_path}")

if __name__ == "__main__":
    generate_csv()
