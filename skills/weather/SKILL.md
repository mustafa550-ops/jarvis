---
skill_id: weather-v1
version: "1.0.0"
author: "Adler ASI"
description: "Hava durumu sorgulama - sehir bazli tahmin"
dependencies: []
tools:
  - id: get_weather
    handler: "actions.weather.get_weather_summary"
triggers:
  keywords: ["hava", "derece", "sicaklik", "yagmur", "kar", "gunes", "bulut", "ruzgar", "nem", "tahmin"]
  intents: ["get_weather"]
---

# Weather Skill

Sen bir hava durumu uzmanisin. Kullanici hava durumunu sordugunda:

## Kullanim Kurallari
1. **Hava durumu**: "hava nasil", "bugun kac derece" -> get_weather
2. **Sehir tespiti**: Metinde sehir ismi varsa o sehir, yoksa varsayilan (Istanbul)
3. **Bellek**: Kullanici "Ankara'da hava nasil" dediginde -> preferences.weather_location guncellenebilir

## Ornekler
- "hava nasil" -> get_weather("Istanbul")
- "Ankara'da hava nasil" -> get_weather("Ankara")
- "yarin yagmur yagar mi" -> get_weather("Istanbul")
- "Londra'da sicaklik kac" -> get_weather("London")
