import flet as ft
import os

class TopBar(ft.UserControl):
    def __init__(self, page, on_settings, on_help, color_scheme):
        super().__init__()
        self.page = page
        self.on_settings = on_settings
        self.on_help = on_help
        self.color_scheme = color_scheme
        self.title = "KAEFER Industrie GmbH"

    def build(self):
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logos", "KAE_Logo_RGB_300dpi2.jpg")
        if os.path.exists(logo_path):
            logo = ft.Image(src=logo_path, width=100, height=40, fit=ft.ImageFit.CONTAIN)
        else:
            logo = ft.Text("KAEFER")

        self.title_text = ft.Text(self.title, size=20, weight=ft.FontWeight.BOLD)
        
        return ft.Container(
            content=ft.Row([
                logo,
                ft.Container(width=20),  # Abstand
                self.title_text,
                ft.Container(expand=True),  # Flexibler Abstand
                ft.IconButton(ft.icons.SETTINGS, on_click=self.on_settings),
                ft.IconButton(ft.icons.HELP, on_click=self.on_help)
            ], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=self.get_color(),
            padding=10
        )

    def get_color(self):
        return getattr(ft.colors, self.color_scheme, ft.colors.SURFACE_VARIANT)

    def update_title(self, new_title):
        self.title = new_title
        self.title_text.value = new_title
        self.update()

    def update_color_scheme(self, new_color_scheme):
        self.color_scheme = new_color_scheme
        self.content.bgcolor = self.get_color()
        self.update()
