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

3. TEAM ON ANY NETWORK (home, travelling, mobile data)  - choose ONE
   A. Cloudflare Tunnel (easiest, free, https, no router changes)
      1) Download cloudflared (free) and save it as cloudflared.exe in this folder.
      2) Keep Run_Server.bat running, then double-click Start_Public_Link.bat.
      3) It prints a link like  https://xxxx.trycloudflare.com  - share it. (It changes every time you start it.)
      4) For a permanent link on your own domain use a "named tunnel" (cloudflared tunnel login / create / route dns).
      5) Then open web_config.json and set  "behind_proxy": true   (so sign-in cookies and IP limits work behind the tunnel).
   B. Tailscale (private network, free for small teams): install Tailscale on the server and on each person's device,
      then they open  http://<server-tailscale-name>:8080  . Nothing is exposed to the internet.
   C. Company server / cloud VM: install Python there, copy this folder, open port 8080 (or put it behind nginx/IIS with https).
   NEVER forward port 8080 on your router straight to the internet without https.

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
   - Forgot the admin password?  python tdms_web.py --reset-admin   (sets it back to admin123).
