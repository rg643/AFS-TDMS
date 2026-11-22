"""
TDMS Dashboard V8
Modern dashboard page for TDMS
"""
import tkinter as tk
import tdms_core as core
import tdms_graphics as g
import tdms_widgets as W
from tdms_widgets import Card, RButton, FONT, P, px

class DashboardPage(W.ScrollFrame):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.app = app
        wrap = tk.Frame(self.inner, bg=P.BG)
        wrap.pack(fill='both', expand=True, padx=px(12), pady=px(12))

        banner = Card(wrap)
        banner.pack(fill='x', pady=(0, px(12)))
        tk.Label(banner.body, text=f'Welcome Back, {app.user["name"]}', bg=P.CARD, fg=P.TITLE,
                 font=(FONT, 20, 'bold')).pack(anchor='w')
        tk.Label(banner.body, text='Technical Document Management System', bg=P.CARD,
                 fg=P.MUTED, font=(FONT, 10)).pack(anchor='w')

        kpi = tk.Frame(wrap, bg=P.BG)
        kpi.pack(fill='x')
        self.kpis = {}
        for title in ('Documents','Storage','Favorites','Users'):
            c = Card(kpi)
            c.pack(side='left', fill='both', expand=True, padx=4)
            v = tk.StringVar(value='0')
            tk.Label(c.body,text=title,bg=P.CARD,fg=P.MUTED,font=(FONT,9)).pack(anchor='w')
            tk.Label(c.body,textvariable=v,bg=P.CARD,fg=P.TITLE,font=(FONT,20,'bold')).pack(anchor='w')
            self.kpis[title]=v

        body = tk.Frame(wrap,bg=P.BG)
        body.pack(fill='both',expand=True,pady=10)

        left = Card(body)
        left.pack(side='left',fill='both',expand=True,padx=(0,5))
        tk.Label(left.body,text='Quick Actions',bg=P.CARD,fg=P.TITLE,font=(FONT,12,'bold')).pack(anchor='w')
        RButton(left.body,'Upload Document',app.add_docs_dialog,'main').pack(anchor='w',pady=2)
        RButton(left.body,'Create Folder',lambda: app.add_cat(False),'navy').pack(anchor='w',pady=2)

        right = Card(body)
        right.pack(side='left',fill='both',expand=True,padx=(5,0))
        tk.Label(right.body,text='Recent Activity',bg=P.CARD,fg=P.TITLE,font=(FONT,12,'bold')).pack(anchor='w')
        self.activity = tk.Listbox(right.body,height=10)
        self.activity.pack(fill='both',expand=True)

        self.refresh()

    def refresh(self):
        st = core.stats(self.app.user['id'])
        self.kpis['Documents'].set(str(st['docs']))
        self.kpis['Storage'].set(core.size(st['size']))
        self.kpis['Favorites'].set(str(st['fav']))
        self.kpis['Users'].set(str(st['users']))

        self.activity.delete(0,'end')
        for r in core.recent_activity(10):
            self.activity.insert('end', f"{r['user']} - {r['action']}")
