# 🧩 Nexidra Modular Plugin Framework

A **self-evolving FastAPI architecture** designed by **Nexidra Technologies** that allows you to:

- Build modular FastAPI plugins dynamically
- Auto-register, verify, and load them at runtime
- Distribute via a secure internal **Plugin Registry**
- Manage lifecycle with a rich **CLI** and **Dockerized stack**

---

## 📁 Folder Structure

```
nexidra/
├── app/                     # Main modular FastAPI app
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── permissions.py
│   │   ├── plugin_loader.py
│   │   ├── plugin_manager.py
│   │   ├── registry_client.py
│   │   └── security.py
│   ├── models/
│   │   └── plugin_model.py
│   ├── plugins/
│   │   ├── sms/
│   │   │   ├── plugin.py
│   │   │   ├── plugin.json
│   │   │   ├── permissions.json
│   │   │   ├── models.py
│   │   │   ├── migrations/
│   │   │   │   └── 1.0.0_init.py
│   │   │   └── templates/
│   │   │       └── dashboard.html
│   ├── manage.py             # CLI manager
│   ├── Dockerfile
│   └── requirements.txt
├── registry/                 # Internal plugin registry service
│   ├── main.py
│   ├── core/
│   │   ├── database.py
│   │   └── security.py
│   ├── routes/
│   │   ├── plugins.py
│   │   └── verification.py
│   ├── models/
│   │   └── registry_model.py
│   ├── uploads/
│   ├── keys/
│   │   ├── private.pem
│   │   └── public.pem
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── .env
```

---

## ⚙️ Environment Configuration

`.env`

```bash
APP_NAME=NexidraModular
ENV=production
MONGO_URL=mongodb://mongo:27017/nexidra
REGISTRY_URL=http://registry:8500/api
VERIFY_KEY_PATH=/app/keys/public.pem
```

---

## 🐳 Docker Deployment

```bash
docker compose up --build
```

**Services started:**

- 🧠 mongo → Database backend
- 🏗️ registry → Internal plugin registry
- ⚙️ app → Main modular FastAPI app

### Access Points

| Service         | URL                       |
| --------------- | ------------------------- |
| Main App        | http://localhost:8000     |
| Plugin Registry | http://localhost:8500/api |
| MongoDB         | mongodb://localhost:27017 |

---

## 🔐 Security Model

Plugins are **digitally signed** at publication using RSA private key  
and **verified** before being loaded using the app’s public key.

### Generate RSA keys:

```bash
mkdir -p registry/keys
openssl genpkey -algorithm RSA -out registry/keys/private.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -pubout -in registry/keys/private.pem -out registry/keys/public.pem
```

---

## ⚙️ Plugin Lifecycle

1. **Create**

   ```bash
   python manage.py plugin new sms
   ```

2. **Develop**
   Modify routes, models, and templates in `/plugins/sms/`.

3. **Discover**

   ```bash
   python manage.py plugin discover
   ```

4. **Publish**

   ```bash
   curl -X POST http://localhost:8500/api/publish         -F "file=@plugins/sms.zip"         -F 'manifest={"name":"sms","version":"1.0.0"}'
   ```

5. **Install**

   ```bash
   python manage.py plugin install sms
   ```

6. **Upgrade**

   ```bash
   python manage.py plugin upgrade sms
   ```

7. **Rollback**

   ```bash
   python manage.py plugin rollback sms
   ```

8. **Verify**

   ```bash
   python manage.py plugin verify-all
   ```

9. **Marketplace Sync**
   ```bash
   python manage.py marketplace sync
   ```

---

## 🧰 CLI Reference

| Command                | Description                  |
| ---------------------- | ---------------------------- |
| plugin list            | Lists all plugins            |
| plugin new <name>      | Create new plugin template   |
| plugin discover        | Scan and register plugins    |
| plugin install <name>  | Install plugin from registry |
| plugin upgrade <name>  | Upgrade plugin               |
| plugin rollback <name> | Rollback to previous version |
| plugin verify-all      | Verify signatures            |
| marketplace sync       | Sync marketplace list        |

---

## 🎨 Plugin Generator Flags

| Flag       | Options                | Description             |
| ---------- | ---------------------- | ----------------------- |
| --db       | mongo, postgres        | Choose database backend |
| --template | basic, chat, dashboard | Select UI template type |
| --author   | string                 | Set author metadata     |

### Examples

```bash
python manage.py plugin new sms --db=mongo
python manage.py plugin new chatbox --template=chat
python manage.py plugin new reports --db=postgres
python manage.py plugin new gallery --author="Elijah Mwa"
```

---

## 🧠 Plugin Structure Example

```
plugins/sms/
├── plugin.py
├── plugin.json
├── permissions.json
├── models.py
├── migrations/
│   └── 1.0.0_init.py
└── templates/
    └── dashboard.html
```

---

## 🏪 Internal Registry API

| Endpoint                       | Description                      |
| ------------------------------ | -------------------------------- |
| POST /api/publish              | Publish plugin (signed + stored) |
| GET /api/plugins               | List verified plugins            |
| GET /api/plugins/{name}/latest | Get latest plugin info           |
| GET /uploads/{file}            | Download plugin zip              |

Each plugin includes:

```json
{
  "name": "sms",
  "version": "1.0.0",
  "checksum": "SHA256...",
  "signature": "RSA...",
  "verified": true
}
```

---

## 🔄 Upgrade Workflow

1. Check registry for new version.
2. Download signed zip.
3. Verify RSA signature.
4. Run migration scripts.
5. Update DB version.
6. Keep rollback archive.

---

## 🧱 Example docker-compose.yml

```yaml
services:
  mongo:
    image: mongo:6
    ports: ["27017:27017"]

  registry:
    build: ./registry
    ports: ["8500:8500"]
    volumes:
      - ./registry/uploads:/app/uploads
      - ./registry/keys:/app/keys:ro

  app:
    build: ./app
    ports: ["8000:8000"]
    depends_on: [registry, mongo]
    volumes:
      - ./app:/app
      - ./registry/keys/public.pem:/app/keys/public.pem:ro
```

---

## 🧱 Data Persistence

Default: MongoDB  
Switch to Postgres → set `USE_POSTGRES=true` in `.env`.

---

## 🚀 Example Developer Flow

```bash
python manage.py plugin new analytics --db=postgres --template=dashboard
python manage.py plugin discover
docker compose up
```

Visit: [http://localhost:8000/analytics](http://localhost:8000/analytics)

---

## 🧾 License

MIT © 2025 Nexidra Technologies

---

Developed by **Elijah Mwa** and **Nexidra Technologies**

# 🧩 Nexidra Modular Plugin Framework

A **self-evolving FastAPI architecture** designed by **Nexidra Technologies** that allows you to:

- Build modular FastAPI plugins dynamically
- Auto-register, verify, and load them at runtime
- Distribute via a secure internal **Plugin Registry**
- Manage lifecycle with a rich **CLI** and **Dockerized stack**
- Publish and sign plugin versions securely with a private key

---

## ⚙️ Nexidra Plugin Manager CLI — Updated

The Nexidra CLI (`manage.py`) is your all-in-one management tool for modular plugins and the internal registry system.

### 📜 Commands Summary

| Command                       | Description                                                    |
| ----------------------------- | -------------------------------------------------------------- |
| `plugin list`                 | Show all locally installed plugins                             |
| `plugin discover`             | Scan `/plugins` folder and sync with DB                        |
| `plugin install <name>`       | Install a plugin from the internal registry                    |
| `plugin upgrade <name>`       | Upgrade plugin to the latest verified version                  |
| `plugin rollback <name>`      | Restore last backup zip                                        |
| `plugin verify-all`           | Verify plugin signatures and checksums                         |
| `plugin publish <name>`       | **Package, sign, version-bump, and upload plugin to registry** |
| `marketplace sync`            | Show available plugins in internal registry                    |
| `migration new <plugin>`      | Create new migration (auto version bump)                       |
| `migration run <plugin>`      | Apply all pending migrations                                   |
| `migration rollback <plugin>` | Rollback last migration                                        |

---

## 🚀 New Command: `plugin publish`

### 📦 Description

Packages, signs, and publishes a plugin to your **Nexidra Registry**.  
This command automatically:

1. Zips the plugin folder under `.plugin_backups/`
2. Reads and bumps the version from `plugin.json`
3. Signs the ZIP with the Nexidra private key
4. Uploads to the internal registry via `RegistryClient.publish_plugin()`

### 🧰 Usage

```bash
python manage.py plugin publish <name>
```

### 🧩 Example

```bash
python manage.py plugin publish sms
```

**Output:**

```
📦 Packaging sms@1.0.0...
🔼 Bumped version 1.0.0 → 1.0.1 before publish
🚀 Published sms@1.0.1 successfully!
✅ Registry confirmed publish
```

---

## 🔑 Requirements

- Environment variable `REGISTRY_API_KEY` must be set:

  ```bash
  export REGISTRY_API_KEY=your_admin_key_here
  ```

- Registry server must support:

  - `POST /plugins/publish` for uploads
  - `GET /plugins`, `/plugins/<name>/manifest`, `/plugins/<name>/download`

- Required local files:
  - `core/registry_client.py` — handles all registry API communication.
  - `core/security.py` — provides signing and verification (`sign_data`, `verify_signature`).
  - Private/public keys in `secrets/private_key.pem` and `secrets/public_key.pem`.

---

## 🧩 Example Workflow

```bash
# 1️⃣ Create a new plugin
python manage.py plugin new sms --template chat

# 2️⃣ Create a migration
python manage.py migration new sms "add sender index"

# 3️⃣ Apply migration locally
python manage.py migration run sms

# 4️⃣ Publish to registry
python manage.py plugin publish sms

# 5️⃣ Verify from registry
python manage.py marketplace sync
```

---

## 🧠 Versioning Notes

- Version bumping uses [semver](https://semver.org/).
- By default, `plugin publish` bumps the **patch** version.
- You can optionally modify the CLI to support `--minor` or `--major` flags.

---

## 🔒 Signing & Verification

Every plugin ZIP is signed using RSA keys under `secrets/`.

| File              | Purpose                                                |
| ----------------- | ------------------------------------------------------ |
| `private_key.pem` | Used to sign plugin bundles during publish             |
| `public_key.pem`  | Used to verify plugin authenticity during installation |

The checksum and signature are stored inside the registry manifest:

```json
{
  "name": "sms",
  "version": "1.0.1",
  "checksum": "a95f...4e2",
  "signature": "30ff9a...",
  "verified": true
}
```

---

## 🧾 Typical Output Flow

```bash
📦 Packaging sms@1.0.0...
🔼 Bumped version 1.0.0 → 1.0.1 before publish
✅ Signed and checksum generated.
🚀 Published sms@1.0.1 successfully!
📘 Registry entry created at https://registry.nexidra.io/plugins/sms
```

---

## 🧰 Dockerized Setup (Optional)

```bash
docker build -t nexidra-modular .
docker run --rm -v $(pwd):/app nexidra-modular python manage.py plugin publish sms
```

---

**Developed by Nexidra Technologies**  
_“Dream. Kreate. Grow.”_
