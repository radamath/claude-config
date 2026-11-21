## Ortam: Linux (VPS / claude.ai cloud)
- XAMPP yok. Skill ve agent'lardaki `C:\xampp\...` yolları bu ortamda geçersiz; Linux karşılıklarını kullan.
- PHP hata logu: `php -i | grep error_log` ile bul. Web sunucusu logları: `/var/log/apache2/` veya `/var/log/nginx/`, servisler için `journalctl -u <servis>`.
- `php -l <dosya>` doğrudan çalışır.
- Cloud oturumları geçici bir VM'dir: claude-mem yoktur, yerel dosyalar oturum bitince kaybolur.
