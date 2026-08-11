You reached the start of the range
2026-08-11 07:33
[2026-08-11 06:36:10] [ERROR   ] discord.ui.view: Ignoring exception in view <BusinessDirectoryView timeout=None children=7> for item <_BusinessLanguageSelect placeholder='🌐 اللغة / Language / Langue' min_values=1 max_values=1 disabled=False id=None>
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/discord/ui/view.py", line 598, in _scheduled_task
    await item.callback(interaction)
  File "/app/cogs/city/businesses.py", line 199, in callback
    view = _BusinessDirectoryPrivateView(self.hub, interaction.user.id, lang)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/cogs/city/businesses.py", line 278, in __init__
    self.add_item(_BusinessLanguageSelect(hub, private_user_id=self.user_id, lang=self.lang, row=2))
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/cogs/city/businesses.py", line 182, in __init__
    super().__init__(
  File "/usr/local/lib/python3.11/site-packages/discord/ui/select.py", line 479, in __init__
    super().__init__(
  File "/usr/local/lib/python3.11/site-packages/discord/ui/select.py", line 254, in __init__
    raise TypeError(f'expected custom_id to be str not {custom_id.__class__.__name__}')
TypeError: expected custom_id to be str not NoneType
