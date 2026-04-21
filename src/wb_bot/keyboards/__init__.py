"""WB bot keyboards.

The package follows a **one submodule per feature area** convention so
that keyboard builders stay small, reviewable and easy to test:

    keyboards/
        main_menu.py        # /start, back-to-main, profile root
        magazines.py        # add / list / pick a store
        reviews.py          # review-reply templates, auto-reply toggles
        reports.py          # general / finance / advertising reports
        tasks.py            # task planner keyboards
        settings.py         # notifications, time zone, language

Each module exposes functions that return aiogram ``InlineKeyboardMarkup``
or ``ReplyKeyboardMarkup``, typed with the callback-data classes from
:mod:`aiogram.filters.callback_data`.
"""
