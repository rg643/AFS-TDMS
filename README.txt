TDMS  -  TECHNICAL DOCUMENT MANAGEMENT SYSTEM  (version 7.1)
============================================================

FILES (keep ALL in ONE folder - the folder where your old tdms_app.py was)
  tdms_app.py        the application (screens, library, dashboard, settings)
  tdms_viewers.py    everything that opens inside a tab (PDF, Word, Excel, pictures, video, links ...)
  tdms_core.py       data, settings, file readers, versions, recycle bin, folder import
  tdms_admin.py      Users, Activity log, Admin (Branding, Rules, Backup)
  tdms_graphics.py   icons, charts, login background
  tdms_widgets.py    buttons, cards, coloured tabs, dialogs, light / dark theme
  tdms_native.py     drag and drop in and out of Windows Explorer
  app_icon.ico/.png, logo.png, Run_App.bat, Build_EXE.bat, Create_Desktop_Shortcut.bat

UPDATING FROM VERSION 5
  1. Close TDMS completely.  2. Copy ALL files into the same folder (replace).  3. Delete "__pycache__".
  4. Run_App.bat  (exe users: run Build_EXE.bat again).   Your data is kept.

WHAT IS NEW IN 7.1  -  SMOOTHER, NO STUCK / FLICKER
  * Pictures (file icons, folder icons, tab icons) are drawn ONCE and reused. Before, every row of every
    list redrew its icon each time - that was the main reason for the stuck feeling.
  * The document list only redraws what changed (favourite, rename, status ...); same list = no redraw.
  * Fonts for the charts are remembered (they were reloaded for every label).
  * Small writes (activity log, preferences such as the last folder) are saved every 2 seconds in one go,
    instead of waiting for the disk (and OneDrive) on every click.
  * Adding big files or a whole folder shows a progress window and the program stays alive (no more
    "not responding"). Copying is done in pieces.
  * The page you leave is hidden, so resizing the window only works on what you see. One shared scroll
    handler (it was added again on every rebuild). Idle timer no longer runs on every mouse move.
  * PDF pages are drawn faster. Selecting many documents does not ask the database about each one.
  * tdms_perf.log (same folder) lists any action that took longer than 0.15 s. If something still feels
    slow, send that file.

WHAT IS NEW IN 7.0
  * Quick type chips above the list: All, PDF, Word, Excel, PPT, Images, Video, Links - one click filters.
  * Clickable folder path: Library > AMR > Dynamo-500 ... click any part to jump there.
  * Preview panel (View > Preview panel): a thumbnail (picture or first page of a PDF) and the facts of the
    selected document without opening it. Off by default so the list keeps the whole width.
  * Status and review date: Details > Status (Draft, In review, Approved, Obsolete) and Review date.
    The Status column is in the list (View > Columns). Dashboard: "Review due in the next 30 days"
    (overdue in red) and "Documents by status".
  * More > "Save selected as ZIP..." packs documents (one folder per library folder).
  * Header: dark / light button next to Sign out. Your photo menu > "Shortcuts and tips".

WHAT IS NEW IN 6.4
  * The window title bar takes the colour of the tab you are on (Library blue, Dashboard green, a PDF red,
    Excel green ...) with white text; dialog windows have a navy title bar. This needs Windows 11
    (Windows 10 cannot colour title bars - it stays as it is).
  * Clicked rows are clearly coloured (blue with white text) in the folder list, the document list and
    other tables; highlighted menu options are coloured in your accent colour.

WHAT IS NEW IN 6.3
  * More room for the document list: one slim row of tools (search, View, Folders, + Add, Open, favourite,
    up / down, select all, Delete, More). Everything about how the list looks is in ONE menu:
    View > Show, Order by, Columns, Compact rows, Details line, Folders panel.
    The "Folders" button hides / shows the folder panel so the list can use the whole width.
  * Recycle bin is always visible at the bottom of the folder list (with the number of items), like a Trash
    folder. Click it to see deleted documents; Restore or Delete forever there.
  * New folder / New subfolder: Manage (above the folder list), right-click a folder, or + Add > New empty
    folder. Folders also come from "+ Add > A folder with its files" (or dragging a folder in).
    Admin: Manage > "Delete folder and its documents" removes a folder with its sub-folders; the documents
    go to the Recycle bin and come back under "Restored documents".
  * Dashboard: every number has a short remark (this week, compared with last week ...), plus a quick
    review row: Recently opened by you, Your favorites, Most opened - double-click to open.

WHAT IS NEW IN 6.2
  * Simple, clean document list: no file colours behind the rows any more - just the coloured file icons,
    soft stripes, a hover highlight and a clear selected row. (If you like colour you can switch on
    "Add a soft colour to each row by file type" in Profile and settings > Preferences.)
  * Dashboard no longer flickers: it is drawn completely first and then shown.
  * Window title bar takes the colour of the header (Windows 11) and the window icon is sharp at small sizes.

WHAT IS NEW IN 6.1
  * Tabs: colour-filled rounded tabs with a soft shadow and an icon. The selected tab is solid colour with
    white text; the others are a soft tint of their colour. Library blue, Dashboard green, Users purple,
    Activity orange, Admin grey; every opened file takes its file colour (PDF red, Excel green ...).
  * Tables: dark-blue column headings and soft colour behind each row by file type (switch it off in
    Profile and settings > Preferences > "Colour the document rows by file type").
  * Header profile now shows your photo, name, e-mail ID and #employee ID, with USER / ADMINISTRATOR.
  * Touchpad: two-finger scrolling is smooth everywhere (lists, tables, text, PDF, pictures, dashboard).
    Pinch in / out zooms PDF and pictures (same as Ctrl + mouse wheel). Shift + wheel scrolls sideways.

WHAT IS NEW IN 6.0
  LIBRARY
  * Your own order: select documents, press  ▲ / ▼  (or Alt+Up / Alt+Down) to move them up or down inside the
    folder. Order box:  My order, Name, Newest, Largest, Type ...   (clicking a column heading also sorts)
  * Compact view button, long file names (sideways scroll bar), Select all, Delete, Add folder, Add web link.
  * Add a whole FOLDER: drag it in, or "Add folder". It becomes a folder with sub-folders in the tree
    and every file inside is added. Click it in the tree to open it.
  * Folder colour: right-click a folder (admin) > Folder colour.
  * File colours: click your photo > My profile and settings > Colours (PDF, Word, Excel, CSV, PowerPoint, image,
    web link, archive, video, audio, text, CAD, other). Each type has a clearly different colour by default.
  * Tabs are colour-coded: Library blue, Dashboard green, Users purple ... and every opened file takes its
    file colour (PDF red, Word blue, Excel green ...).
  OPENING FILES INSIDE A TAB
  * PDF: scroll up/down through all pages like Adobe, zoom (Ctrl+wheel), Fit width, Find, page box.
    SELECT TEXT with the mouse (double-click selects a word) and copy it with Ctrl+C or "Copy text".
  * Excel (.xlsx) and CSV open as tables (CSV no longer opens as Notepad; "Edit as text" is a button).
    Choose "First row = headings"; Ctrl+C copies the selected rows.
  * Word .docx, PowerPoint .pptx: built-in view. The button "Exact view (PDF)" shows the real pages.
  * Old formats .doc .xls .ppt (and .rtf .odt): shown exactly through Microsoft Office on this PC
    (a few seconds the first time). If Office is not installed they open in their own program.
  * Pictures: zoom with + / - / Ctrl+wheel, Fit, 100%, drag to move. Double-click toggles Fit / 100%.
  * Video and audio: play inside the tab (play, pause, stop, seek, volume). If Windows cannot play a
    format, use "Open in program".
  * Web links (.url files): double-click opens the page in your browser. "Add web link" makes one.
  DASHBOARD
  * 8-10 number tiles, uploads per day, documents by type, 12-week trend, storage by type, top folders,
    top contributors, recently added, largest files, and (admin) recent activity. The page scrolls.

SIGN IN / ADMIN / DRAG AND DROP / RECYCLE BIN / VERSIONS
  Same as version 5 (see Admin > Backup > About).  Drag files in from any drive; drag documents out to Explorer.
  Delete = Recycle bin (restore for 30 days).  More > New version / Version history.

SHORTCUTS
  Ctrl+F search all   Ctrl+N add documents   F2 rename   Delete recycle   Alt+Up/Down move document or folder
  Ctrl+C / Ctrl+V files   Ctrl+W close tab   Ctrl+Tab next tab   Ctrl+A select all

NOTES
  * PDF viewer add-on (one-time): the first PDF shows an Install button (needs internet).
  * Any error is written to tdms_error.log (same folder) - send it to your developer.
