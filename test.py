from selenium import webdriver
from selenium.webdriver.chrome.service import Service

options = webdriver.ChromeOptions()
service = Service(r"E:\SchoolContents\2026-TableNet- A Large-Scale Table Dataset with L\chromedriver-win64\chromedriver.exe")

driver = webdriver.Chrome(service=service, options=options)
driver.get("https://www.baidu.com")
print(driver.title)
driver.quit()