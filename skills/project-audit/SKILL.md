---
name: project-audit
description: Bir projenin tam sağlık denetimi. "projeyi incele", "denetle", "audit", "bu proje ne durumda", "teknik borç" istendiğinde güvenlik, kod kalitesi, yapı ve performans açısından tarar ve önceliklendirilmiş iyileştirme listesi çıkarır. Dosya değiştirmez.
---

# Proje Denetimi

Salt okunur. Hiçbir dosyayı değiştirme.

## 1. Keşif
- Klasör yapısı, giriş noktaları (`index.php`, router), config dosyaları, veritabanı bağlantı yöntemi, kullanılan kütüphaneler (`composer.json`, `package.json`), PHP sürüm uyumluluğu.
- Git reposu mu? Son commit'ler, `.gitignore` var mı?

## 2. Paralel denetim
Kullanıcı ekip istediyse veya proje büyükse şu agent'ları paralel çalıştır, yoksa aynı kontrolleri kendin yap:
- `security-auditor` — tüm proje
- `code-reviewer` — en kritik 5-10 dosya (giriş, kimlik doğrulama, veri yazan sayfalar)

## 3. Ek kontroller
- Tekrarlanan kod blokları ve kopyalanmış dosyalar (`- Kopya`, `.bak`, `_old`).
- Web kökünde açıkta duran hassas dosyalar (`.sql`, `.env`, `phpinfo.php`, yedekler).
- Hata yönetimi ve loglama.
- Döngü içinde sorgu, `SELECT *`, sayfalama eksikliği.

## 4. Rapor
```
# <Proje> Denetim Raporu

## Genel not: A/B/C/D/F — tek cümle gerekçe

## Hemen düzeltilmeli (kritik)
1. ... — dosya:satır — neden — nasıl

## Kısa vadede
## Uzun vadede / teknik borç
## İyi olanlar
```
Raporun sonunda: "Hangi maddeden başlayalım?" diye sor.
