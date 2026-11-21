---
name: bug-hunt
description: Sistematik hata ayıklama. Bir hata, beklenmeyen davranış, beyaz sayfa, 500 hatası, yanlış veri veya "çalışmıyor" şikayeti geldiğinde kök nedeni bulup minimal düzeltmeyi yapar. Semptom yamalamayı yasaklar.
---

# Hata Avı

Kural: Kök nedeni kanıtlamadan düzeltme yazma.

## 1. Tekrarla
- Hatayı tetikleyen tam adımları, girdiyi ve beklenen/gerçek sonucu yaz.
- Logları oku: XAMPP için `C:\xampp\apache\logs\error.log`, `C:\xampp\php\logs\php_error_log`, varsa uygulamanın kendi logu. Tarayıcı hatalarında konsol ve ağ isteklerine bak.
- Tekrarlayamıyorsan bunu söyle ve gerekli bilgiyi iste.

## 2. Daralt
- Hatanın oluştuğu yerden geriye doğru veri akışını izle: girdi → işleme → sorgu → çıktı.
- Hipotez kur, her hipotezi tek bir gözlemle doğrula veya çürüt. Rastgele değişiklik yapma.
- Gerekirse geçici log ekle — ve işin sonunda mutlaka kaldır.

## 3. Kök neden
Tek cümleyle yaz: "X olduğunda Y, çünkü Z." Bu cümleyi yazamıyorsan henüz bulmadın.

## 4. Düzelt
- Kök nedeni çözen en küçük değişikliği yap.
- Aynı hatanın kod tabanında başka yerlerde olup olmadığını `grep` ile ara ve kullanıcıya bildir.

## 5. Doğrula
- Orijinal tekrarlama adımlarıyla hatanın gittiğini göster.
- Değişen PHP dosyalarına `php -l`.
- Geçici log/debug kodunu kaldırdığını kontrol et.

## Rapor
```
Semptom: ...
Kök neden: ...
Düzeltme: dosya:satır — ne değişti
Doğrulama: ...
Benzer riskli yerler: ...
```
