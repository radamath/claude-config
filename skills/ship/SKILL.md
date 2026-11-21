---
name: ship
description: Değişiklikleri GitHub'a gönderme hattı. "commit at", "pushla", "PR aç", "gönder", "GitHub'a yükle" denildiğinde ön kontrolleri yapar, sırları engeller, Conventional Commit mesajı yazar, dal açar, push eder ve gerekirse PR oluşturur.
---

# Ship — Commit / Push / PR

Bu skill yalnızca kullanıcı açıkça commit/push/PR istediğinde çalışır.

## 1. Durum
- `git status`, `git branch --show-current`, `git remote -v`.
- Repo değilse: kullanıcıya sor, onay gelirse `git init`, uygun `.gitignore` oluştur (PHP: `vendor/`, `.env`, `*.log`, `config.local.php`, yedek dosyaları; Node: `node_modules/`).
- Global `user.name`/`user.email` yoksa kullanıcıya sor; kendin uydurma.

## 2. Ön kontroller (biri başarısızsa dur)
- Sır taraması: staged dosyalarda şifre, API anahtarı, token, connection string ara (`password`, `api_key`, `secret`, `token`, `BEGIN PRIVATE KEY`). Bulursan commit etme, kullanıcıya bildir.
- Büyük/istenmeyen dosyalar: `vendor/`, `node_modules/`, `.sql` dump, `.zip`, 5 MB üzeri dosyalar.
- Değişen PHP dosyalarına `php -l`; varsa test ve lint komutlarını çalıştır.
- Debug kalıntısı: `var_dump`, `print_r`, `console.log`, `dd(`.

## 3. Dal
- `main`/`master` üzerindeysen yeni dal aç: `feat/…`, `fix/…`, `refactor/…`, `chore/…`.

## 4. Commit
- Dosyaları isimleriyle ekle; körü körüne `git add -A` yapmadan önce listeyi gözden geçir.
- Mesaj: `type(scope): kısa açıklama` + boş satır + neden yapıldığı. Bir commit = bir mantıksal değişiklik.
- Sistemin istediği Co-Authored-By satırını ekle.

## 5. Push ve PR
- `git push -u origin <dal>`.
- PR istendiyse `gh pr create` — başlık commit tarzında; gövde: Ne değişti, Neden, Nasıl test edildi, Riskler.
- PR linkini kullanıcıya ver.

Asla: force-push, `--no-verify`, başkasının dalına push, onaysız `main`'e push.
