AFS TDMS  -  WEB VERSION 8.0
==============================
The same document system, in the browser. Your team opens a link - no installation on their computers.
Works on Windows PCs, Macs, tablets and phones (Chrome, Edge, Safari, Firefox).

1. START THE SERVER (one computer, for example your laptop or an office PC)
   - Copy this whole folder to the PC that will act as the server.
     TIP: put it in the SAME folder as the desktop program: it then uses the same data (AFS_TDMS_Data):
     all your users, folders, documents and versions are already there.
   - Double-click  Run_Server.bat.  The first time it installs Flask / Pillow / Waitress (needs internet once).
   - The window shows the addresses, for example
         On this computer :  http://localhost:8080
         On your network  :  http://192.168.1.25:8080
   - Keep that window open while people use it. Press Ctrl+C to stop.
   - First sign-in: Administrator tab, user  admin   password  admin123  -> you are asked to change it.

2. TEAM IN THE SAME OFFICE / WIFI / VPN
   - Run  Open_Firewall.bat  once (right-click > Run as administrator).
   - Send the team the "On your network" address. They sign in with their email ID and password
     (or use "Create account" if you allowed it; you approve them on the Users tab).

3. TEAM ON ANY NETWORK (home, travelling, mobile data, other offices)  - choose ONE
   Your team then only needs the https link. No software on their computers, no VPN.
   The server PC must be ON and Run_Server.bat must be running.

   A. QUICK TRY - Cloudflare Tunnel (free, no account, 3 minutes)
      1) Download  cloudflared-windows-amd64.exe  from Cloudflare (free), rename it  cloudflared.exe,
         put it in this folder.
      2) Keep Run_Server.bat running. Double-click  Start_Public_Link.bat.
      3) It prints a link like  https://xxxx.trycloudflare.com  - send it to your team.
      Good: very easy.  Limit: the link CHANGES every time you start it.

   B. PERMANENT LINK - Tailscale Funnel (free, no domain, https, same link every day)   <- recommended
      One-time setup (about 10 minutes):
      1) On the server PC install Tailscale (tailscale.com/download) and sign in (Google or Microsoft account).
      2) Open  login.tailscale.com/admin/dns  and switch ON "MagicDNS" and "HTTPS Certificates".
      3) Keep Run_Server.bat running. Double-click  Start_Tailscale_Funnel.bat.
         The first time it shows a web address: open it and click "Enable Funnel", then run the file again.
      4) It prints your permanent link, for example  https://afs-pc.tail1234.ts.net  - share it with the team.
      After this, the link keeps working whenever the server PC is on and Run_Server.bat is running.
      Switch it off any time:  tailscale funnel reset

   C. Company server / cloud VM: install Python there, copy this folder, put it behind https (IIS / nginx / Caddy).

   SAFETY CHECKLIST BEFORE SHARING A PUBLIC LINK
      - Change the admin password (the program asks you) and use a long one.
      - Admin page > Rules: keep "New accounts must be approved" ON and set your company e-mail domain.
      - Wrong passwords are limited per address and per account, and everything is in the Activity log.
      - Big files: they are sent in pieces automatically, so videos of 1 GB work even through the tunnel.
      - NEVER forward port 8080 on your router straight to the internet without https.
      - Inside the office you can still use the plain address (section 2) - it is faster.

4. KEEP IT RUNNING
   - Install_Autostart.bat starts the server when you sign in to Windows.
   - The PC must be on. For 24x7 use a small always-on PC or server.

5. WHAT YOU CAN DO IN THE BROWSER
   - Library: folders (admin: new / rename / move / colour / delete), documents list, search, type chips
     (PDF, Word, Excel, PPT, Images, Video, Links), sort, columns, compact rows, preview panel.
   - Add: Upload files, upload a whole FOLDER, or drag files / folders onto the list. Same name -> new version / keep both / skip.
   - Open in tabs: PDF (browser viewer: zoom, search, select text), pictures (zoom, drag, pinch), video and audio,
     Word / PowerPoint (text view), Excel and CSV (tables, sheets), text files (edit and save), web links.
   - Download one file or "Save selected as ZIP". Favorites, versions and history, Recycle bin with restore.
   - Status (Draft, In review, Approved, Obsolete) and review date, with reminders on the Dashboard.
   - Dashboard: numbers, quick review lists, charts, review due, status, recent activity (admin).
   - Users (admin): approve, add, edit, reset password, disable, delete. Activity log with CSV export.
   - Admin: logo, names, colours, login background, rules (sign-up, approval, e-mail domain, password length,
     max file size, Recycle bin days), database backup download, addresses to share.
   - Dark / light theme, profile photo, security question for password recovery, file type colours.
   - The page updates itself when other people add documents.

6. GOOD TO KNOW
   - Data lives in AFS_TDMS_Data next to the program: tdms.db, files\, photos\, backups\. Back up this folder.
     The Admin page can also download a copy of the database. A daily backup is made automatically.
   - Word / Excel / PowerPoint: the browser shows the text and tables. "Exact view (PDF)" appears when the SERVER is a
     Windows PC with Microsoft Office. Old .doc / .xls / .ppt: Exact view or Download.
   - PDF thumbnails in the preview panel need:  pip install pymupdf   (optional).
   - Do not run the desktop program and the web server on the same data at the same time (use one of them).
   - Security: passwords are stored hashed (PBKDF2); sign-in is limited after repeated mistakes; web pages cannot run
     uploaded HTML; every action is in the Activity log. Use https (tunnel) when outside your office.
   - Change the port in web_config.json ("port": 8080). Errors are written to tdms_web_error.log.
   - Public link with Cloudflare / Tailscale: nothing to configure; the server trusts the tunnel automatically.
   - Forgot the admin password?  python tdms_web.py --reset-admin   (sets it back to admin123).
