# claude-config: Claude Code ayarlarını tek kaynaktan dağıtma — Tasarım

Tarih: 2026-11-21
Durum: Taslak (onay bekliyor)

## Amaç ve neden

Kullanıcı skill, MCP, plugin, agent ve global kuralları (CLAUDE.md) **bir kez, Windows makinesinde** kuruyor.
Bunların ayrıca uğraşmadan şu ortamlarda, eski/yeni her projede ve her oturumda hazır olması isteniyor:

1. Windows — Claude Code CLI ve Claude Code Windows (desktop) uygulaması
2. Kullanıcının VPS'indeki Claude Code
3. claude.ai/code cloud oturumları

Bugün (1) zaten `~/.claude` üzerinden ortak. (2) ve (3) için hiçbir şey yok; her şey elle tekrar kuruluyor.

## Hedefler

- Windows'taki `~/.claude` **tek doğruluk kaynağı**dır (tek yönlü dağıtım: Windows → GitHub → VPS / cloud).
- Dağıtılanlar: `CLAUDE.md`, `skills/`, `agents/`, `commands/` (varsa), plugin + marketplace listesi, user-scope MCP sunucuları.
- Windows'ta silinen bir skill/agent hedeflerden de silinir.
- Windows'ta yeni bir şey kurulduktan sonra elle bir şey yapmak gerekmez (otomatik senkron).

## Hedef olmayanlar

- Çift yönlü senkron (VPS/cloud'da yapılan değişiklikler geri gelmez).
- claude-mem hafıza veritabanının paylaşılması (ayrı iş; claude-mem'in kendi cloud-sync'i var).
- Sohbet geçmişi, oturum dosyaları, `.credentials.json`, token'lar.
- macOS desteği.

## Anti-hedefler (çalışsa bile başarısızlık sayılır)

- **Herhangi bir sırrın GitHub'a gitmesi.** (API anahtarı, token, `.env`, credentials)
- Hedef makinede kullanıcının elle kurduğu, depoda olmayan bir şeyin silinmesi/ezilmesi.
- Windows'a özel bir ayarın (ör. Windows yolu içeren hook) Linux'a taşınıp orada Claude Code'u bozması.

## Kısıtlar (doğrulanmış)

- GitHub hesabı: `radamath`, `gh` ile oturum açık. Depo **private** olacak.
- Cloud oturumları yerel `~/.claude`'u görmez. Ortam başına bir **setup script** tanımlanabilir: oturum başında,
  Claude Code başlamadan, Ubuntu 24.04 üzerinde root olarak çalışır; GitHub proxy'si üzerinden Claude GitHub
  App'in kurulu olduğu private depoları çekebilir.
- Cloud setup sonucu **snapshot olarak ~7 gün önbelleklenir**; script veya izinli hostlar değişince ya da önbellek
  dolunca yeniden çalışır. → Cloud tarafı en fazla ~7 gün gecikmeli güncellenebilir (bkz. Riskler).
- Cloud ortam değişkenleri ortamı kullanan herkese açıktır; sırlar için "network secret" kullanılmalı.
- Cloud, claude.ai'de etkinleştirilen skill'leri zaten otomatik yükler (yedek yol).
- Mevcut `~/.claude/settings.json` içinde `thedotmack` (claude-mem) marketplace'i `extraKnownMarketplaces`'te
  **yok**, sadece `plugins/known_marketplaces.json`'da var → export bunu tamamlamalı.
- `~/.claude/skills/synced/` claude.ai tarafından yönetilen bir klasör → dağıtılmaz.

## Yaklaşımlar

| | Yaklaşım | Artı | Eksi |
|---|---|---|---|
| **A (seçildi)** | Ayrı private depo + Windows'ta beyaz listeli export (`sync`) + Linux'ta `install.sh` | Sırlar yapı gereği dışarıda; Windows'ta sorunsuz; hedeflerde sadece kendi yönettiği dosyalara dokunur | Export adımı gerekir (hook ile otomatik) |
| B | `~/.claude`'u doğrudan git deposu yapmak | Az parça | Credentials/geçmiş aynı klasörde, tek `.gitignore` hatası sızıntı; Windows symlink sorunları |
| C | Sadece claude.ai skill senkronu + connector | Depo yok | Plugin, agent, CLAUDE.md, yerel MCP taşınmaz; VPS tam kapsanmaz |

Kullanıcı A'yı seçti.

## Tasarım

### Depo düzeni (`radamath/claude-config`, private)

```
claude-config/
  CLAUDE.base.md            # ortak kurallar
  CLAUDE.windows.md         # Windows eki
  CLAUDE.linux.md           # VPS + cloud eki   → ~/.claude/CLAUDE.md = base + ek
  .secretscan-allow         # sır taraması istisnaları
  skills/<ad>/...           # → ~/.claude/skills/<ad>/
  agents/*.md               # → ~/.claude/agents/
  commands/*.md             # → ~/.claude/commands/   (varsa)
  plugins.json              # marketplaces + etkin plugin'ler
  mcp.json                  # user-scope MCP'ler, sırlar ${VAR} yer tutucu
  targets.json              # hedefe göre hariç tutmalar (ör. cloud: claude-mem yok)
  scripts/
    sync.ps1                # Windows: export → sır taraması → commit → push
    install.sh              # Linux (VPS + cloud): uygula
    cloud-setup.sh          # cloud ortam setup script'inin içeriği
  docs/
```

### Windows: `sync.ps1`

1. `~/.claude`'dan **sadece beyaz listedekileri** depo klasörüne kopyalar (CLAUDE.md, skills hariç `synced/`,
   agents, commands). Depodaki karşılığı Windows'ta artık olmayan öğeler depodan silinir.
2. `plugins.json` üretir: `settings.json → enabledPlugins` (true olanlar) + her plugin'in marketplace kaynağı
   (`extraKnownMarketplaces` ∪ `plugins/known_marketplaces.json`). Yerel yollar (`installLocation`) yazılmaz.
3. `mcp.json` üretir: `~/.claude.json → mcpServers` (user scope). `env` değerleri ve `headers` değerleri
   `${MCP_<SUNUCU>_<ANAHTAR>}` yer tutucularıyla değiştirilir; gerçek değerler asla yazılmaz.
4. **Sır taraması (fail-closed):** bilinen token desenleri (`sk-`, `ghp_`, `github_pat_`, `xox`, `AKIA`,
   `-----BEGIN`, `CLAUDE_CODE_OAUTH_TOKEN=` vb.) ve `.env`/`credentials` dosya adları. Bulgu varsa commit atmaz,
   hatayı loglar ve çıkar.
5. Değişiklik varsa `chore: sync claude config` commit'i + push. Değişiklik yoksa hiçbir şey yapmaz.
6. Çıktıyı `~/.claude-config/sync.log`'a yazar; hiçbir zaman interaktif soru sormaz.

**Otomatik tetikleme:** Windows `~/.claude/settings.json`'a `SessionEnd` hook'u eklenir → `sync.ps1`.
Bu hook **Windows'a özeldir ve dağıtılmaz** (settings.json zaten dağıtılmıyor, sadece plugin listesi türetiliyor).
Elle çalıştırma da mümkün.

### Linux: `install.sh [--target vps|cloud]`

1. Depo içeriğini yerleştirir: CLAUDE.md, skills, agents, commands → `~/.claude/`.
2. **Manifest** (`~/.claude/.claude-config-manifest`): install.sh'nin kurduğu dosya/klasör listesi.
   Bir sonraki çalışmada depodan kalkmış ama manifest'te olan öğeler silinir; manifest'te olmayanlara
   (kullanıcının elle kurdukları) **dokunulmaz**.
3. Plugin'ler: `claude plugin marketplace add <kaynak>` + `claude plugin install <ad>@<marketplace>`,
   zaten kuruluysa atla. `targets.json` hariç tutmalarına uyar.
4. MCP'ler: her sunucu için `${VAR}`'lar hedefteki sır dosyasından doldurulur, `claude mcp add-json -s user`.
   Bir değişken eksikse o MCP atlanır ve loglanır (yarım/boş anahtarla kurulmaz).
5. İdempotent: aynı içerikle tekrar çalışınca bir şey değiştirmez.

### VPS

- Depo `~/.claude-config/repo`'ya **salt okunur deploy key** ile klonlanır.
- Sırlar: `~/.claude-config/secrets.env` (chmod 600, depoda yok).
- `systemd` timer (cron yoksa/tercih edilirse cron) her 15 dk: `git pull --ff-only && install.sh --target vps`.

### Cloud (claude.ai/code)

- Claude GitHub App `claude-config` deposuna kurulur.
- Kullanılan cloud ortam(lar)ının setup script'ine `cloud-setup.sh` içeriği konur: depoyu klonlar,
  `install.sh --target cloud` çalıştırır.
- `targets.json`: cloud'da claude-mem kurulmaz (geçici VM, hafıza tutamaz, token ister).
- MCP sırları cloud'da network secret olarak tanımlanır; tanımlı değilse o MCP atlanır.

### İnceleme sonrası kararlar

**Kullanıcının kararları**

1. **İsim çakışması:** Hedefte aynı isimde, install.sh'nin kurmadığı bir skill/agent/plugin/MCP varsa
   **depo kazanır**. Eskisi `~/.claude-config/backup/<zaman damgası>/` altına yedeklenir, öğe manifest'e alınır
   ve bundan sonra düzen tarafından yönetilir. Depoda olmayan, elle kurulmuş öğelere hâlâ dokunulmaz.
2. **Hedefe özel içerik:** Global kurallar parçalara ayrılır:
   - `CLAUDE.base.md`: ortak kurallar, her hedefe gider
   - `CLAUDE.windows.md`: XAMPP/PowerShell/Windows yolları
   - `CLAUDE.linux.md`: VPS + cloud ekleri

   Kurulumda `CLAUDE.md = base + hedef eki` olarak birleştirilir. Windows'ta da aynı birleştirme yapılır;
   kaynak dosyalar `~/.claude/claude-config/` altında tutulur. İlk ayırmayı Claude yapar, kullanıcı onaylar.
   Windows'a bağlı skill/agent'lar `targets.json`'da hedef bazında hariç tutulabilir (ör. `bug-hunt` → sadece windows).

**Claude'un kararları** (kullanıcı itiraz edebilir)

3. **Ayna davranışı:** Plugin ve MCP'ler de manifest'te izlenir. Windows'ta kaldırılan veya devre dışı bırakılan
   plugin hedefte de kaldırılır. Config'i değişen MCP yeniden eklenir. Plugin sürüm güncellemeleri her makinenin
   kendi otomatik güncellemesine bırakılır; sürüm sabitlenmez.
4. **Hata görünürlüğü:** `sync.ps1` sonucunu `~/.claude-config/last-sync.json`'a yazar. Windows'ta bir
   `SessionStart` hook'u son senkron başarısızsa oturum başında tek satır uyarı gösterir. VPS'te `install.sh`
   da aynı yöntemle durumunu yazar.
5. **Sır taraması:** Bir bulgu senkronun **tamamını** durdurur (kısmi push yok, fail-closed). Bilinen zararsız
   eşleşmeler için depoda `.secretscan-allow` dosyası bulunur: dosya yolu + desen bazında istisna, gerekçe yorumuyla.
6. Symlink olan skill'ler (ör. `find-skills` → `~/.agents/skills`) gerçek içerikleriyle kopyalanır.
7. Şu an user-scope MCP yok. MCP yolu birim testle doğrulanır; gerçek veriyle ilk MCP kurulduğunda tekrar denenir.

## Riskler / doğrulanacaklar

1. **Cloud'da `~/.claude/settings.json` ve `claude plugin install` davranışı belirsiz.** Doküman "user settings
   not read" diyor; bu yerel makinenin dosyası için mi, VM içindeki dosya için de mi geçerli net değil.
   → Uygulamanın ilk adımı olarak cloud'da küçük bir deneme (spike) yapılacak. Plugin'ler cloud'da
   çalışmazsa: skill/agent/CLAUDE.md taşınır, plugin'lerin cloud kısmı "desteklenmiyor" olarak raporlanır.
2. **Cloud ~7 gün gecikme.** Snapshot önbelleği yüzünden. Azaltma: `sync.ps1` çıktısında uyarı +
   gerekirse setup script'ine küçük bir değişiklik yaparak yeniden çalıştırma talimatı. Tam çözüm yok.
3. **Windows'a özel MCP komutları** (`cmd /c npx ...`): Linux'ta `cmd /c` sarmalayıcısı soyulur;
   Windows'a özel yol içeren MCP'ler `targets.json`'da işaretlenip atlanır.
4. VPS'te Claude Code yoksa/eskiyse install.sh bunu tespit edip durur ve söyler (kendisi kurmaz).

## Uygulayıcıya bırakılanlar

- Sır tarama desenlerinin tam listesi, log formatı, script iç yapısı.
- systemd timer vs cron seçimi (VPS'e bakınca).

## Kullanıcıdan uygulama sırasında istenecekler

- VPS: SSH host/kullanıcı, işletim sistemi, Claude Code kurulu mu.
- Cloud: GitHub App'in depoya kurulması ve setup script'inin claude.ai'de yapıştırılması (UI'da kullanıcı yapar).
