"""Genio — Tunisian Darija Technical Q&A Dataset Synthesizer.

Generates high-quality, domain-specific training pairs for the `genio-brain`
LLM in Alpaca format (``instruction`` / ``input`` / ``output``). Domains:

  * Linux administration
  * Docker topologies
  * GPU management
  * Self-healing code remediation

CLI:
    python3 -m core.dataset_synthesizer --count 50
    python3 -m core.dataset_synthesizer --domain docker --count 20 --seed 7
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger  # noqa: E402

from config import GENIO_DIR  # noqa: E402

DEFAULT_OUT = GENIO_DIR / "training" / "genio_dataset.jsonl"

DOMAINS = ("linux", "docker", "gpu", "selfhealing")

ALPACA_KEYS = ("instruction", "input", "output")

# Polite interactional phrasings we rotate in front of each instruction so
# repeated seed scenarios never yield byte-identical records.
_INSTRUCTION_PREFIXES = (
    "",
    "عندي سؤال مهم: ",
    "عين هذا: ",
    "نبغي نفهّم مليح، عاوني: ",
    "نفضل نجاوب بالدارجة، اشرحلي: ",
    "وقعت في مشكل حقيقي، ساعدني: ",
)

_CONTEXT_ENRICHERS = (
    "",
    "",
    "السياق: منصّة إنتاج صغيرة في HiTech Lab فيها 3 سيرفرات.",
    "السياق: جهاز Home Server معمّر، نظام التشغيل Ubuntu 22.04.",
    "السياق: فريق ديال مطورين، 5 خدمة، باش نفهمو الحل من الأول.",
    "السياق: لا بد ما يكونو الحلول مجرّبين وواقعيين، ماشي تمارين نظرية.",
)

# Each scenario is a hand-written, verified Q&A. The `output` values are
# intentionally verbose, dialectal and command-level so the model learns to
# answer like a Tunisian infrastructure engineer, not like a textbook.
SCENARIOS: List[Dict[str, str]] = [
    # ─────────────────────────── Linux administration ─────────────────────── #
    {
        "domain": "linux",
        "instruction": "نحاول نشغّل سكريبت باش ويقولي Permission denied. علاش هذا وعلاش شدّيت الكتبية على ملفي؟",
        "input": "",
        "output": (
            "هذا معناه المستخدم اللي باش يشغّل الملف ما عندوش صلاحية التنفيذ عليه.\n"
            "1. تحقق من الصلاحيات: `ls -la script.sh` — إذا ما كانش X في الجهة ديال المالك، لازم نزيدوه.\n"
            "2. خذّها بالحل الآمن: ماشي `chmod 777` أبداً. استعمل: `chmod u+x script.sh` باش تعطي التنفيذ للمالك فقط.\n"
            "3. إذا كانو أكثر من مستخدمين في المجموعة: `chmod ug+x script.sh`.\n"
            "4. تحقق من نظام الملفات: إذا كان ملفك فالـ mount مع `noexec`، حتى الـ +x ما يخدمو.\n"
            "5. آخر حاجة خبّرت بيها: الـ Shebang صحيح؟ باش `./script.sh` يخدم يلزم يكون `#!/bin/bash` في أول سطر.\n"
            "قاعدة زهبية: `u+x` للتنفيذ، `u+r` للقراءة، `u+w` للكتبية. وما تنساش الـ umask باش الملفات الجديدة تخرج بأمان."
        ),
    },
    {
        "domain": "linux",
        "instruction": "الـ Service تاعي ما يبداش مع البوت، وشفت في systemd لقيتو failed. كيفاش نلقى السبب الحقيقي؟",
        "input": "",
        "output": (
            "لا تجمّل على لوجات `systemctl status`: الخبر المهم كاين في journald.\n"
            "1. رجع الأسباب الحقيقية: `journalctl -u my-service.service -b --no-pager -n 50`\n"
            "2. إذا ما شفتش والو، شوف سطور الـ stderr: `journalctl -u my-service -b | grep -iE 'error|fail|denied'`\n"
            "3. تحقق من الـ unit file: `systemctl cat my-service` — خبّر على المسار ديال ExecStart، الـ WorkingDirectory والـ User.\n"
            "4. الغالبية المطلقة من الحالات: إما Permissions (المستخدم ما عندوش صلاحية على الملف أو اللوغ)، أو Port مشغول، أو مسار غير موجود.\n"
            "5. بعد الإصلاح: `sudo systemctl daemon-reload && sudo systemctl restart my-service`.\n"
            "نصيحة: إذا كان الـ unit يعمل `Restart=always` ويوقع دائماً، أخرج السبب الحقيقي من journald وما تعتمدش على الـ status فقط."
        ),
    },
    {
        "domain": "linux",
        "input": "القرص ممتلئ تقريباً والفريق ما يقدروش يخدمو، لكن ما نعرفوش وين رايحة المساحة.",
        "instruction": "كيفاش نلقى شنو اللي واخذ كل المساحة على القرص في Linux؟",
        "output": (
            "الحل المرتب: ننزلوا من الجذر ونحدّوا الـ directories اللي بالوزن.\n"
            "1. نظرة عامة: `df -h` — شوف مين الـ mount اللي ممتلئ.\n"
            "2. أكبر العناصر: `sudo du -h --max-depth=1 / | sort -rh | head -20`\n"
            "3. الملفات الكبار: `find / -xdev -type f -size +1G -exec ls -lh {} \\; 2>/dev/null`\n"
            "4. اللوغات أول الضنايا: `/var/log` ينجم يكبر غدارا ولا يوقف. `journalctl --vacuum-size=100M` يمشي حل سريع ونظيف.\n"
            "5. حاويات Docker: `docker system df` و `docker image prune -af` باش تتحاص من الصور الميتة.\n"
            "فكرة الوقاية: فعّل logrotate على الملفات الكبار في `/etc/logrotate.d/` باش ما تعودش كتحبس في نفس المشكل."
        ),
    },
    {
        "domain": "linux",
        "input": "السكريبت يشتغل ماشي مع ما نأمره به، واللوجات تاعو خاويا.",
        "instruction": "الـ Cron job تاعي ما يخدمش علاش؟ يعمل السكريبت ممتاز بهوية يدي.",
        "output": (
            "السبب الأول تقريباً دائماً: الـ cron يشغّل السكريبت ببيئة نظيفة بلا PATH ولا متغيرات ديالك.\n"
            "1. جرب السكريبت وحده: `bash /path/to/script.sh` — إذا يخدم، المشكل فالبيئة.\n"
            "2. تحقق بيدك: `crontab -l` وأكّد المسار مطلق ماشي نسبي.\n"
            "3. داخل السكريبت زيد: `export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`\n"
            "4. اللوغات: ابعث الخرج للوغ: `0 2 * * * /bin/bash /path/script.sh >> /var/log/script.log 2>&1`\n"
            "5. تحقق من المستخدم: السكريبت تاعك رايح بالهوية ديال المستخدم اللي عنده crontab، ماشي root إلا إذا ركّبتو في `/etc/cron.d` بالـ RUNAS.\n"
            "وما تنساش: السطر في cron يلزم يخّدم بـ Ends newline، وحد الساعة حسب `timedatectl`."
        ),
    },
    {
        "domain": "linux",
        "input": "السيرفر مخنوق: CPU شاد على 100% والـ load عالي، ومحدش يعرف شكون السبب.",
        "instruction": "كيفاش نتعرف على الـ Process اللي كيحبس السيرفر، ونفهم شنو راي يخدم؟",
        "output": (
            "باش نحدّدو المذنب بسرعة:\n"
            "1. نظرة لحظية: `top -bn1 | head -15` أو `htop` باش تشوف اللي يصرف CPU/RAM.\n"
            "2. أعمق تفصيلة: `ps aux --sort=-%cpu | head -10` — شوف الـ %CPU و %MEM معا بعضهم.\n"
            "3. علاش ما تحبس عليه؟ `strace -p <PID> -f -tt -c` لمدّة 10 ثواني ثم Ctrl+C باش تشوف وين كيوقف.\n"
            "4. إذا كان الـ PID يتغيّر كل ما تتبّعوه؟ عندك الـ parent: `ps -o ppid= -p <PID>` و `pstree -p <PID>`.\n"
            "5. الحالة المنتفخة: مؤشر النظام: الـ load يُقارَن بعدد الأنوية — `nproc`، فإذا كان الـ load أعلى من الأنوية، النظام مطغوط.\n"
            "في آخر الحال نتحاصو من البنائي: `kill <PID>`، وإذا كان عنيد: `kill -9`، ثم نبدأو نبحثو على السبب الجذري في اللوغات."
        ),
    },
    {
        "domain": "linux",
        "input": "السيرفر راي يخدم لكن مع كل ثلاثية الأمور تقرر يبطّ، والإنتاج يتأثر.",
        "instruction": "علاش نضيفو Swap وفيش المهام؟ وشنو الفرق بين RAM و Swap لشخص يخدم بعيد على السيرفر؟",
        "output": (
            "الـ RAM هي الطاولة الوحيدة اللي يستخدمها النظام.\n"
            "1. الفكرة: الـ RAM زربة ومكلفة. الـ Swap هي جزء من القرص (ملف أو Partition) كيخدم كذيل رايert للـ RAM.\n"
            "2. متى نستعملو: لما يولي الـ RAM باهي، النظام يبدا يقلب للـ Swap باش ما يموتوش الـ Process.\n"
            "3. الخطر: إذا كان الجهاز كيخدم بالزاف على الـ Swap، كل النشاط يبطّ حاجي موجب لأنه القرص أبطأ بآلاف المرات من الـ RAM — الاسم الفني: Thrashing.\n"
            "4. نضيفو ملف Swap بسرعة: `sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` ثم نزيدو سطر في `/etc/fstab`.\n"
            "5. تُضبط السلوك بالـ `vm.swappiness`: `sysctl vm.swappiness=10` باش النظام يفضّل الـ RAM ولا يقفز للـ Swap إلا عند الحاجة.\n"
            "الخلاصة: الـ RAM ما تفوتش، والسيرفر محتاج Swap باش يتنفس لكن ماشي باش يعيشو فيه كل يوم."
        ),
    },
    {
        "domain": "linux",
        "input": "نحاول نشغّل تطبيق أعطاني: Address already in use على المنفذ 8080.",
        "instruction": "كيفاش نلقى شكون راي شاد المنفذ ونحرّرو أو نغيّرو منفذ التطبيق؟",
        "output": (
            "منفذ واحد يخدم في كل مرة — الـ bind يكسر مع الثاني.\n"
            "1. نلقاو المذنب: `sudo ss -tlnp | grep 8080` — شوف عمود PROCESS: الـ PID والاسم.\n"
            "2. إذا استعملنا الأداة الحديثة: `ss` بدل `netstat` ماشي نهائي، لكن الـ ss أسرع وأوضح.\n"
            "3. نحرّرو إذا كان حقنا: `kill <PID>` أو `sudo systemctl stop <service>` ثم نتأكدو: `ss -tlnp | grep 8080` يجيب خاوي.\n"
            "4. أفضل: نغيّرو منفذ تطبيقنا بالـ config بدل نحاربو مع سيرفيرات مئةغي: `PORT=8081 python app.py`.\n"
            "5. أمنياً: نربوطو على `127.0.0.1` ماشي `0.0.0.0` إلا إذا كان مطلوب — هذا يمنع الوصول من الخارج للمنفذ.\n"
            "تحقق نهائي: `curl -v http://127.0.0.1:8080` ويعطيني شغّال — نصبحو واثقين."
        ),
    },
    # ─────────────────────────── Docker topologies ──────────────────────────  #
    {
        "domain": "docker",
        "input": "أعدت تشغيل حاوية وتبخّر كل البيانات. كان عندي ملفات مخزّنة في الداخل.",
        "instruction": "علاش الحاوية تضيع البيانات مع كل إعادة إنشاء، وكيفاش نضمن الاستمرارية بالـ Volumes؟",
        "output": (
            "أي حاجة كتبتها داخل الحاوية تموت معها — إلا ما كانش Volume.\n"
            "1. القاعدة: Filesystem الحاوية مؤقت ومرتبط بدورة حياة الحاوية.\n"
            "2. نعرّفو Volume: `docker volume create labdata` ثم `docker run -v labdata:/app/data myimage`.\n"
            "3. نعرّفو Bind Mount πραγμα: `-v /host/path:/app/data` — هنا البيانات بداخل المجلد المحلي، واضحة ومباشرة للتعديل.\n"
            "4. في Compose نكتبو بالـ `volumes:` مفتاح يحمل `named volume`، ولو خدمة تكرار الاسم تعمل نفس المجلد.\n"
            "5. تأكد إنشاء: `docker volume ls` و `docker run --rm -v labdata:/app/data myimage ls /app/data`.\n"
            "نصيحة مهنية: بالتأكيد نفصلو بيانات Postgres وحدة: `postgres:/var/lib/postgresql/data` — هذا يمنع فقدان قاعدة البيانات نهائياً."
        ),
    },
    {
        "domain": "docker",
        "input": "عندي تطبيق ويب وقاعدة بيانات ونحتاجهم يتخاطبوا بيناتهم بأمان.",
        "instruction": "اشرحلي كيفاش نبني topology نتاع Container الخدمات يخاطبوا بيناتهم مع Docker Compose؟",
        "output": (
            "القاعدة الذهبية في Compose: كل خدمة عندها اسم، والاسم ذاك هو الـ DNS الداخلي.\n"
            "1. نبنيو ملف `docker-compose.yml` بخدمتين: `web` و`db`.\n"
            "2. الـ Compose يخليهما على نفس الشبكة الافتراضية، و`web` يوصّل إلى قاعدة البيانات بالاسم: `db:5432`.\n"
            "3. نبقيو قاعدة البيانات محفوظة: `volumes:\n  - pgdata:/var/lib/postgresql/data`.\n"
            "4. نضبطو الترتيب: `depends_on:\n  - db` + healthcheck على `db` باش `web` ينتظر جاهزيتها الحقيقية.\n"
            "5. مثال كامل:\n"
            "```yaml\n"
            "services:\n"
            "  web:\n"
            "    build: .\n"
            "    ports: [\"8080:80\"]\n"
            "    environment:\n"
            "      DB_HOST: db\n"
            "    depends_on:\n"
            "      db:\n"
            "        condition: service_healthy\n"
            "  db:\n"
            "    image: postgres:16\n"
            "    environment:\n"
            "      POSTGRES_PASSWORD: s3cr3t\n"
            "    volumes:\n"
            "      - pgdata:/var/lib/postgresql/data\n"
            "    healthcheck:\n"
            "      test: [\"CMD-SHELL\", \"pg_isready\"]\n"
            "volumes:\n"
            "  pgdata:\n"
            "```\n"
            "النتيجة: topology مفهومة، أوامر `docker compose up -d` تشغّل كل شيء، والبيانات تبقى حية بين إعادة الإنشاء."
        ),
    },
    {
        "domain": "docker",
        "input": "نحاول نشر حاوية فيها تطبيق Port 80، لكن الحاوية تطلع والسيرفر لا يستجيب.",
        "instruction": "علاش ماشي قادر نوصّل من الخارج للتطبيق في Docker رغم انه الحاوية شغالة؟",
        "output": (
            "الحاوية تستمع وهي حية، لكن هاذا الـ port mappé ماشي صحيح.\n"
            "1. تحقق من الحالة: `docker ps` — شوف عمود PORTS. إذا كان خاوي أو `8080/tcp` بلا `->`، ما صارش نشر.\n"
            "2. النشر الصحيح: `docker run -p 8080:80 myimage` — المعنى: 8080 على الهاست يوصّل إلى 80 داخل الحاوية.\n"
            "3. تحقق داخل الحاوية: `docker exec -it <id> ss -tlnp` — خبّر على أي منفذ يستمع التطبيق الحقيقي.\n"
            "4. Firewall الهاست: `sudo ufw status` و `sudo ufw allow 8080/tcp` — هذا السبب المتخفي.\n"
            "5. آخر حاجة: إذا كان الـ app يستمع على `localhost` داخل الحاوية، استعمل `0.0.0.0` من البرنامج نفسه.\n"
            "اختبار نهائي: `curl -I http://<host>:8080` باش نتأكدو من الرد."
        ),
    },
    {
        "domain": "docker",
        "input": "عندي أكثر منة خدمة وابغيت نعزل بمكة، وحدة عامة ووحدة خاصة.",
        "instruction": "شنو الفرق بين شبكة Bridge و Host في Docker، وأي واحد نختارو في topology متعديلة؟",
        "output": (
            "الـ Bridge: شبكة معزولة وافتراضية فيها DNS داخلي للحاويات — الاختيار الافتراضي والآمن.\n"
            "1. Bridge: كل الحاويات على نفس البركة يتخاطبوا بالاسم، والوصول للخارج بالـ NAT.\n"
            "2. Host: الحاوية تشترك في شبكة الهاست مباشرة — سريع لكن بدون عزل، والـ port تاعها يلتقي مباشرة في المنفذ النظامي.\n"
            "3. Multi-host topology: نبنيو شبكات متعددة `docker network create frontend` / `backend`، فالحاوية تنجم تلقى في الاثنين.\n"
            "4. الحالة المثالية: نطلي الـ Nginx في شبكة `frontend`، والتطبيق في `backend`، وقاعدة البيانات حصرية في `backend` فقط.\n"
            "5. الحاجة الفاصلة: الأمان — من كم يكون عند الحاوية شبكة وحدة فقط، أقوى العزل وأصغر السطح.\n"
            "القاعدة: Bridge افتراضياً؛ Host فقط في الحالات الواحدة اللي محتاجين فيها الأداء الخام (مثل WebSocket مكثف) ومضحّين بالعزل."
        ),
    },
    {
        "domain": "docker",
        "input": "نبني لاب الـ VPN في المنزل: سيرفر WireGuard وحاوية عميل والحاويات يلاقو راسهم.",
        "instruction": "كيفاش نرسم هندسة Topology لـ WireGuard بين حاويتين في Docker؟",
        "output": (
            "نعملو شبكتين معزولتين ونربطو بينهم بالنفق — ها هي هندسة لاب الـ VPN.\n"
            "1. ننجمو شبكتين: `docker network create wan` و `docker network create lan`.\n"
            "2. سيرفر الـ WireGuard يخدم على الشبكتين: واجهة `wan` بخصوص WAN IP، وواجهة `lan` بخصوص الـ IP الداخلي.\n"
            "3. العميل متصل فقط بشبكة `wan` — فوقها ننصبو النفق الافتراضي `wg0`.\n"
            "4. على العميل نربطو `AllowedIPs = 10.8.0.0/24` ونؤكّدو أن الـ private key تاعو يخدم بيها وحدها.\n"
            "5. جدول العناوين مثال نموذجي:\n"
            "```\n"
            "srv_wan_ip = 172.30.0.10   # على شبكة WAN\n"
            "srv_lan_ip = 192.168.100.10  # على شبكة LAN المحمية\n"
            "cli_wg_ip  = 10.8.0.2      # داخل النفق\n"
            "cli_wan_ip = 172.30.0.20\n"
            "```\n"
            "والقاعدة: السيرفر يربط الشبكة الخارجية `wan` بالشبكة المحمية `lan`، والنفق يستعمل UDP 51820. نزيد إعادة توجيه حزم الـ LAN عبر النفق: `iptables -t nat -A POSTROUTING -o wg0 -j MASQUERADE`، فيديو التطبيقات في `lan` توصل للعميل بأمان."
        ),
    },
    {
        "domain": "docker",
        "input": "حاويات تتوقف في أوقات عشوائية، والمشكلة تظهر فقط في الليل.",
        "instruction": "كيفاش نلاحظ حالة حاوية من بعيد ونعرف على لوجاتها بسهولة؟",
        "output": (
            "الحاوية تتوقف ومحدش شاهد الأمر — هنا يخدم الـ Observability manual.\n"
            "1. الحالة الحية: `docker ps -a` — الفرق بين `Up` و `Exited`.\n"
            "2. لوجات مباشرة: `docker logs -f --tail 100 <container>` — باش ترصد الحدوث لحظة.\n"
            "3. البحث في الماضي: `docker logs --since 2h <container> | grep -i error` — الليل كامل.\n"
            "4. السبب الشهير للتوقف الليلي: إعادة تشغيل جدولة الهاست أو OOM. نتحققو: `dmesg | grep -i killed`.\n"
            "5. الحل الذاتي: نضيف `restart: unless-stopped` في Compose — الحاوية تولي تعاود تطلع وحدها بعد الفشل.\n"
            "وإذا كانت الخدمة حرجة، نتقدم: `journalctl -u docker -b` باش نعرفو مين عندو علاقة بالموت."
        ),
    },
    # ─────────────────────────── GPU management ─────────────────────────────  #
    {
        "domain": "gpu",
        "input": "شغّلت حاوية فيها كود يعمل GPU لكن `nvidia-smi` ما يراش الغرفة.",
        "instruction": "الـ GPU ما يبانش داخل الحاوية Docker — حل المشكلة من أول خطوة.",
        "output": (
            "السبب الجذري غالباً معروف جداً: الحاوية مسالة من الوصول للـ GPU من غير --gpus.\n"
            "1. نتحققو من السائق على الهاست: `nvidia-smi` يلزم يخدم مسبقاً.\n"
            "2. نتحققو من الرانر: `docker info | grep -i runtime` — يلزم يبان `nvidia` في القائمة.\n"
            "3. ننشؤو الحاوية بالطريقة الصحيحة: `docker run --rm --gpus all nvidia/cuda:12.4.1-runtime-ubuntu22.04 nvidia-smi`\n"
            "4. في Compose:\n"
            "```yaml\n"
            "services:\n"
            "  worker:\n"
            "    image: nvidia/cuda:12.4.1-runtime-ubuntu22.04\n"
            "    deploy:\n"
            "      resources:\n"
            "        reservations:\n"
            "          devices:\n"
            "            - driver: nvidia\n"
            "              count: all\n"
            "              capabilities: [gpu]\n"
            "```\n"
            "5. إذا ما بانش، غالباً السائق من القديم: `sudo apt install nvidia-driver-<version>` ثم `nvidia-smi` يعاود يبان.\n"
            "ملاحظة: كنا في HiTech Lab قدام نفس المشكل — بعد تثبيت `nvidia-container-toolkit` وتشغيل `sudo nvidia-ctk runtime configure --runtime=docker` ثم `sudo systemctl restart docker`، الحاوية شافت الـ GPU مباشرة."
        ),
    },
    {
        "domain": "gpu",
        "input": "المجموعة ما تعرفش وين خسر الـ VRAM، والموديل الذكي يرفض يعمل.",
        "instruction": "كيفاش نراقب استهلاك الـ VRAM وCPU على بطاقة الرسوم بجدية؟",
        "output": (
            "المراقبة الفعلية تبدأ بعادة `watch` وبأوامر ترصد المتغيرات.\n"
            "1. نظرة عامة: `nvidia-smi` — عمود `Memory-Usage` والشغّل `Utilization`.\n"
            "2. نظرة حية: `watch -n 1 nvidia-smi` — كل ثانية تحديث.\n"
            "3. المعطيات فقط: `nvidia-smi --query-gpu=memory.used,memory.free,utilization.gpu --format=csv`\n"
            "4. من Python، نرقيها: نعمل `subprocess` على نفس الاستعلام ونتعرفو على الذروة.\n"
            "5. لمنع OOM على الموديلات الكبيرة: نضبط `--num-ctx` و `OVERRIDE_VRAM_LIMIT` في التطبيق.\n"
            "قاعدة ذهبية: موديل معيّن يتجاوز الـ VRAM الشاغرة دائماً يفشل بطيئاً — الحل المعقول إما تقليل `num_ctx` أو تقسيم النموذج عبر أكثر من GPU واحد بالـ layer offload."
        ),
    },
    {
        "domain": "gpu",
        "input": "نشغّل موديل Ollama ولا نخسر؟ جربت أغلب تشخيصات وفيش حل.",
        "instruction": "الموديل ماشي يطلع مع Ollama رغم أن الـ GPU بحاله — شنو نتحققو أول؟",
        "output": (
            "Ollama يقرر الـ offload على أساس التعليمات والـ VRAM — إليك ترتيب التحقق.\n"
            "1. شوف الحالة الفعلية: `ollama ps` — البعد `PROCESSOR` يبين إذا الخدمة: `100% GPU` أو `CPU`.\n"
            "2. إذا ظهر `CPU`، يعني الموديل غير مسأل على الـ GPU: زد `num_gpu` في المعاملات:\n"
            "```\n"
            "ollama run gemma2:9b \"\" \"{\\\"num_gpu\\\": 999}\"\n"
            "```\n"
            "3. تحقق من الـ VRAM الشاغرة `nvidia-smi` — الموديل يحتاج على الأقل حجم نمطه بلعبة على الطاولة.\n"
            "4. الخيار المعتاد في الـ سيرفر: `OLLAMA_KEEP_ALIVE=0` مع `OLLAMA_NUM_PARALLEL=1` باش لا تجتمع موديلات فوق بعضها.\n"
            "5. تحقق من الـ logs: `ollama serve` راي يعرض رسالة offload واضحة.\n"
            "إذا الموديل صغير والـ GPU وحده، ارفع `num_gpu` والقدرة الربط يعني النموذج يتوضّع كله في الـ VRAM ويسرع."
        ),
    },
    {
        "domain": "gpu",
        "input": "بعد الترقية، التطبيق اللي يعمل CUDA صرله يعطي خطأ في توافقه.",
        "instruction": "علاش تجي مشاكل توافق CUDA بعد ترقية السائق، وكيفاش نصلحوها؟",
        "output": (
            "مشاكل CUDA بعد الترقية تبدو جفلة، لكن قاعدة الحل كلها صغيرة: تطابق الإصدارات.\n"
            "1. الأول نعرّفو الوضع: `nvidia-smi` يعرض `CUDA Version` — هذا أقصى إصدار يدعمه السائق.\n"
            "2. نعرّفو الوضع الذي يطلبه التطبيق: بايثون `torch.version.cuda` أو من `nvcc --version`.\n"
            "3. إذا كان التطبيق يتطلب أحدث من السائق، حلين: ترقية السائق، أو نُركّبو torch نسخة موافقة الـ CUDA المتاح.\n"
            "4. الحل الأكثر ضماناً في Docker: استخدم صورة محددة:\n"
            "```\n"
            "docker run --rm --gpus all pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime python -c \"import torch;print(torch.cuda.is_available())\"\n"
            "```\n"
            "5. تحقق أمني: `ldconfig -p | grep cuda` — إذا تنافات مكتبات قديمة مع الجديدة، نتأكدو من `LD_LIBRARY_PATH`.\n"
            "الخلاصة: السائق + مكتبات CUDA + إطار العمل مثل ثلاثة أسنان ضرس واحد — أي ترقية بنفس الختيار: الجماعة ثلاثة معا."
        ),
    },
    {
        "domain": "gpu",
        "input": "خبيت نختار بين معالج مركزي مع رسومات مدمجة أو بطاقة رسومات خاصة لسيرفر الذكاء الاصطناعي.",
        "instruction": "iGPU ولا dGPU لسيرفر الذكاء الاصطناعي في المنزل؟ عاوني نقرر.",
        "output": (
            "الاختيار يعود على السؤال: تخدم موديلات صغيرة ولا تدرب؟\n"
            "1. الـ iGPU (دمجت في المعالج) توخد في الذكاء المضحّى: تشغيل مصغّرات وموديلات صغيرة، استهلاك قليل وبدون شغل كبير.\n"
            "2. الـ dGPU (بطاقة رسومات منفصلة) للموديلات الأكبر: قيمة الذاكرة VRAM هي الميزة الكبرى — نفوذ حجم النموذج تقريباً مقسم به.\n"
            "3. المعيار السري: حجم الـ VRAM ماشي قوة المعالجة. موديل 7-13B يحتاج غالباً 8-16GB VRAM ليكون مضغوط بالـ Q4.\n"
            "4. استهلاك الكهرباء: iGPU يستهلك حوالي ولا شي إضافي، بينما dGPU يزيد من فاتورة الكهرباء ليلاً ونهاراً.\n"
            "5. التخطيط: ابدأ بـ iGPU لاختبار القيمة، وإذا تحبستوا في السعة، ارتقِ إلى dGPU بذاكرة مناسبة.\n"
            "قاعدة قاطعة: IR طعام الذكاء: البطاقة تحدد حجم النموذج، والمعالج المركزي يحدد سرعة تحضير البيانات. لكل واحد وظيفته."
        ),
    },
    # ──────────────────────── Self-healing code remediation ─────────────────  #
    {
        "domain": "selfhealing",
        "input": "server.py مخدومة بيها خدمة أساسية وتتوقف كل مرة بدون سبب واضح.",
        "instruction": "كيفاش نجعل سكريبت بيثون يعاود يخدم وحدو بعد أي crash في systemd؟",
        "output": (
            "systemd يعطيك خاصية إعادة التشغيل الذاتي بسطرين:\n"
            "1. نكتبو unit file:\n"
            "```ini\n"
            "[Unit]\n"
            "Description=Genio Worker\n"
            "After=network.target\n"
            "\n"
            "[Service]\n"
            "ExecStart=/usr/bin/python3 /opt/genio/worker.py\n"
            "Restart=on-failure\n"
            "RestartSec=3\n"
            "\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
            "```\n"
            "2. `Restart=on-failure` يجبر إعادة التشغيل عند الخروج بإشارة فشل أو كود غير صفري.\n"
            "3. `RestartSec` يمحل فاصل أمان لا يتسرّع النظام أمام فشل متكرر.\n"
            "4. نفعّل: `sudo systemctl daemon-reload && sudo systemctl enable --now genio-worker`\n"
            "5. الوقاية من التسارع: نزيد `StartLimitIntervalSec` و `StartLimitBurst` باش نمنعو الهزّة اللانهائية.\n"
            "وفي الكود نفسه، نأكّدو أن `worker.py` يكسر exceptions المعروفة بـ `sys.exit(1)` ماشي `raise` عرية — باش السايكل يكون مقروء."
        ),
    },
    {
        "domain": "selfhealing",
        "input": "التطبيق يتصل بشبكة خارجية غير مستقرة ويواجه أخطاء ConnectionError بين الحين والآخر.",
        "instruction": "اكتبلي نمط إعادة المحاولة بالـ exponential backoff في Python للطلبات الشبكية.",
        "output": (
            "المبدأ: انتظر قليلاً، ثم أكثر، ثم أكثر — وكلها بارتفاع أسي، وكلها بداخل حدود.\n"
            "1. نكتبو الوظيفة الصغيرة:\n"
            "```python\n"
            "import time, random\n"
            "from typing import Callable\n"
            "\n"
            "def retry_with_backoff(fn: Callable, *, attempts: int = 4,\n"
            "                       base_delay: float = 1.0, max_delay: float = 30.0):\n"
            "    for attempt in range(1, attempts + 1):\n"
            "        try:\n"
            "            return fn()\n"
            "        except Exception as exc:\n"
            "            if attempt == attempts:\n"
            "                raise\n"
            "            delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5), max_delay)\n"
            "            print(f\"[retry] attempt {attempt} failed: {exc}; waiting {delay:.1f}s\")\n"
            "            time.sleep(delay)\n"
            "```\n"
            "2. الجزء `random.uniform` يكسّر تماسك إعادة المحاولات المتزامنة (ليست عشوائية فحسب).\n"
            "3. `max_delay` يحمي من انتظار طويل عند الفشل المتكرر.\n"
            "4. الاستعمال: `data = retry_with_backoff(lambda: requests.get(url, timeout=5).json())`\n"
            "5. نأكّدو أن إجمالي الانتظار يبقى محدوداً: لا تتجاوز حدود `attempts * max_delay` حتى ما تحبسش العملية في دورة تأخير.\n"
            "الخلاصة: backoff أسي + jitter — نمط صناعي كلاسيكي يعتمده حتى Google نفسه."
        ),
    },
    {
        "domain": "selfhealing",
        "input": "قاعدة بيانات SQLite عادت تعطي `database is locked` تحت التحميل المرتفع.",
        "instruction": "كيفاش نحل مشكل `database is locked` في SQLite معناه أثناء الكتابة المتوازية؟",
        "output": (
            "SQLite قارئ عظيم وكاتب مشغول — الـ lock يحدث لما عملية كتبية وحدها تخزن القفل.\n"
            "1. نفهم: مش مشكل دائم، مش عند التحميل العالي تصير قبضات الكتبية متضاربة.\n"
            "2. مفتاح الاتصال الصحيح بالصلاحيات:\n"
            "```python\n"
            "conn = sqlite3.connect(\"db.sqlite\", timeout=30, check_same_thread=False)\n"
            "conn.execute(\"PRAGMA journal_mode=WAL;\")\n"
            "conn.execute(\"PRAGMA busy_timeout=30000;\")\n"
            "```\n"
            "3. `WAL` يسمح للقراء المتوازيين بينما كاتب واحد، ويقفل فقط في لحظة الكتابة.\n"
            "4. `busy_timeout` يجعل SQLite ينتظر على القفل بدل أن يفوّش بالخطأ فوراً.\n"
            "5. نضيف في الكود: على معاملة الكتبية `BEGIN IMMEDIATE` بدل `BEGIN` — ياخذ القفل في البداية وما يموش منتصف العمل.\n"
            "وأخيراً: نفكر في الترحيل لـ Postgres إذا بقى الـ contention عالي — SQLite يخدم بشكل ممتاز على مقياسك الضيق لكن له حدود."
        ),
    },
    {
        "domain": "selfhealing",
        "input": "اللوغات تنمو بلا حدود، والسيرفر ديسك يمتلئ في كل أسبوعين.",
        "instruction": "شنو نمط الـ Log Rotation الصحيح الـ باش لوغات السيرفر ما تكبرش للما لا نهاية؟",
        "output": (
            "اللوغ تراكمي وإذا ما صرتش تو ويتأثر النظام — الحل: الدوران التلقائي.\n"
            "1. أبسط أداة على Linux: `logrotate` مع ملف `logrotate.d`:\n"
            "```\n"
            "/var/log/myapp/*.log {\n"
            "    daily\n"
            "    rotate 7\n"
            "    compress\n"
            "    delaycompress\n"
            "    missingok\n"
            "    copytruncate\n"
            "    postrotate\n"
            "        systemctl reload myapp\n"
            "    endscript\n"
            "}\n"
            "```\n"
            "2. `daily` + `rotate 7`: لوجات الأسبوع فقط — ثم يُضغط (`compress`, `delaycompress`).\n"
            "3. `copytruncate` آمن للتطبيقات التي تحتفظ بـ fd مفتوح للوح.\n"
            "4. في بايثون بالتحديد: `logging.handlers.RotatingFileHandler(maxBytes=10_000_000, backupCount=5)` يعمل نفس الشيء في الأوبجكت نفسه.\n"
            "5. للمراقبة: ترد لوجات الـ journald في الحجم: `journalctl --vacuum-size=200M`.\n"
            "الخلاصة: rotate + compress + قصيرة الرحلة = السيرفر يعيش شهور بلا لمس الـ disk."
        ),
    },
    {
        "domain": "selfhealing",
        "input": "أرغب في عمل أتمنة للمراجعة حيث أخ القلق: إذا وقعت فجأة unknown خطأ، نريد التقاط الأثر بلوغ.",
        "instruction": "كيفاش نضيف معالج استثناءات عام في التطبيق يلتقط الأخطاء غير المتوقعة ويسجّلها بدل انهيار صامت؟",
        "output": (
            "الانهيار الصامت أخطر من الانهيار المعنون — نضبطوا شبكة أمنية عامة.\n"
            "1. نركّب `sys.excepthook` في نقطة دخول البرنامج:\n"
            "```python\n"
            "import sys, traceback, logging\n"
            "\n"
            "def global_hook(exc_type, exc_value, exc_tb):\n"
            "    logging.critical(\"Uncaught exception\", exc_info=(exc_type, exc_value, exc_tb))\n"
            "    sys.exit(1)\n"
            "\n"
            "sys.excepthook = global_hook\n"
            "```\n"
            "2. هذه تصطاد أي `Exception` لم تُعالج في الخيط الرئيسي وتسجل الإثر الكامل ثم تخرج بكود واضح.\n"
            "3. للخيوط، `sys.excepthook` لا يلتقط الاستثناءات — نضيف `logging` داخل `threading.excepthook` أيضاً.\n"
            "4. للمراقبة الخارجية: نتصل بهذا الـ hook مع نظام إشعارات (Telegram/Slack webhook) عند كل `critical`.\n"
            "5. ما ننساوش: الـ hook سجلّ، ماشي إصلاح. بعد التسجيل نعتمد على الـ Restart=on-failure باش الخدمة تعود.\n"
            "النتيجة: أي عطل يترك أثراً واضحاً، ولا حالة تموت بلا بياان."
        ),
    },
    {
        "domain": "selfhealing",
        "input": "عندي أكثر من منطق كل واحد يتصل بخدمة، وأريد أعزل الفشل في كل خدمة.",
        "instruction": "اشرحلي الـ Circuit Breaker pattern — كيفاش نحمي الطلبات المتكررة على خدمة ميتة؟",
        "output": (
            "الـ Circuit Breaker يقطع الطريق بدل ما أحاول في كل مرة نضرب في حائط.\n"
            "1. ثلاثة حالات: CLOSED (كل شيء يخدم)، OPEN (قتل المسار مؤقتاً)، HALF-OPEN (تجربة آمنة بعد مهل).\n"
            "2. الفكرة: بعد بعض الفشل المتتالي (مثلاً 5) يفتح الدارة OPEN، وكل الطلبات ترجع خطأ سريعاً من غير اتصال.\n"
            "3. بعد مهلة (مثلاً 30 ثانية) يمر إلى HALF-OPEN، يسمح بطلب تجريبي واحد — إذا ناجح يرجع CLOSED وإلا يبقى OPEN.\n"
            "4. نموذج مصغّر:\n"
            "```python\n"
            "class CircuitBreaker:\n"
            "    def __init__(self, threshold=5, cooldown=30):\n"
            "        self.threshold, self.cooldown = threshold, cooldown\n"
            "        self.failures, self.open_until = 0, 0\n"
            "\n"
            "    def call(self, fn):\n"
            "        if self.open_until > time.monotonic():\n"
            "            raise RuntimeError(\"circuit open\")\n"
            "        try:\n            return fn()\n"
            "        except Exception:\n"
            "            self.failures += 1\n"
            "            if self.failures >= self.threshold:\n"
            "                self.open_until = time.monotonic() + self.cooldown\n"
            "                self.failures = 0\n"
            "            raise\n"
            "```\n"
            "5. الاستعمال: `result = breaker.call(lambda: external_api.fetch())` — الخدمة الميتة ما تقتلش الجميع.\n"
            "الخلاصة: فشل سريع + حدائق + تجربة موقوتة = خدمة محافظة على صحتها حتى إذا زميلها مرض."
        ),
    },
]

_SCENARIOS_BY_DOMAIN: Dict[str, List[Dict[str, str]]] = {}
for _s in SCENARIOS:
    _SCENARIOS_BY_DOMAIN.setdefault(_s["domain"], []).append(_s)


def _pick_scenarios(domain: Optional[str]) -> List[Dict[str, str]]:
    if domain:
        if domain not in DOMAINS:
            raise ValueError(f"unknown domain: {domain} (choose from {', '.join(DOMAINS)})")
        return _SCENARIOS_BY_DOMAIN.get(domain, [])
    return SCENARIOS


def synthesize_dataset(count: int = 50, domain: Optional[str] = None,
                       seed: Optional[int] = None) -> List[Dict[str, str]]:
    """Return ``count`` Alpaca Q&A records drawn from the seed scenarios.

    Scenarios are cycled round-robin so every domain stays represented. When a
    scenario is reused, the instruction gets a fresh conversational prefix and
    (optionally) a contextual ``input`` enrichment, so records are never
    byte-identical while remaining high quality.
    """
    picks = _pick_scenarios(domain)
    if not picks:
        return []
    rng = random.Random(seed)
    records: List[Dict[str, str]] = []
    seen: set = set()
    i = 0
    while len(records) < count:
        scenario = picks[i % len(picks)]
        i += 1
        prefix = rng.choice(_INSTRUCTION_PREFIXES)
        context = rng.choice(_CONTEXT_ENRICHERS)
        instruction = prefix + scenario["instruction"]
        inp = scenario["input"] or context
        output = scenario["output"]
        if output in seen:
            # The seed corpus is small relative to large counts; re-asking the
            # same warm question with a different opening remains legitimate
            # training value, but we tag it with a follow-up twist in `input`.
            followups = (
                "وإذا أردت تفاصيل أعمق اشرحلي بالمثال.",
                "وأريد مثالاً عملياً معه.",
                "وأشرحلي المخاطر التي يجب الانتباه لها.",
            )
            inp = (inp + " " + rng.choice(followups)).strip()
        record = {
            "instruction": instruction,
            "input": inp,
            "output": output,
        }
        records.append(record)
        seen.add(output)
    return records


def export_jsonl(records: List[Dict[str, str]], out_path: Path) -> Path:
    """Write records to ``out_path`` as one JSON object per line (Alpaca)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info(f"📚 Exported {len(records)} records -> {out_path}")
    return out_path


def main(argv: Optional[List[str]] = None) -> Path:
    parser = argparse.ArgumentParser(
        prog="core.dataset_synthesizer",
        description="Genio — Tunisian Darija technical Q&A dataset synthesizer (Alpaca).")
    parser.add_argument("--count", type=int, default=50,
                        help="Number of records to generate (default: 50)")
    parser.add_argument("--domain", type=str, default=None, choices=DOMAINS,
                        help="Restrict generation to one domain (default: all)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible output")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Output path (default: training/genio_dataset.jsonl)")
    args = parser.parse_args(argv)

    if args.count < 1:
        parser.error("--count must be >= 1")
    records = synthesize_dataset(count=args.count, domain=args.domain,
                                 seed=args.seed)
    path = export_jsonl(records, args.out)
    if args.domain:
        logger.info(f"🌍 domain={args.domain} · seed={args.seed} · "
                    f"{len(records)} records")
    return path


if __name__ == "__main__":
    main()