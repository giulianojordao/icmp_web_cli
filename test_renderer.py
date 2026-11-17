import pathlib
import unittest
from terminal_renderer import render_html


class RendererTests(unittest.TestCase):
    def test_render_original_page(self):
        html = pathlib.Path(__file__).with_name("index.html").read_bytes()
        screen = render_html(html, width=88, color=False)
        self.assertIn("Uma página.", screen)
        self.assertIn("Zero HTTP.", screen)
        self.assertIn("ICMP Echo", screen)
        self.assertIn("768 bytes", screen)
        self.assertNotIn("font-family", screen)
        self.assertNotIn("<div", screen)

    def test_links_and_lists(self):
        screen = render_html('<h2>Olá</h2><ul><li>Um</li><li><a href="https://example.org">Link</a></li></ul>', color=False)
        self.assertIn("## Olá", screen)
        self.assertIn("• Um", screen)
        self.assertIn("Link (https://example.org)", screen)

    def test_strip_terminal_control_characters_and_script(self):
        screen = render_html('<p>Oi\x1b[31m vermelho</p><script>alert(1)</script>', color=False)
        self.assertNotIn("\x1b", screen)
        self.assertNotIn("alert(1)", screen)

    def test_color_optional(self):
        plain = render_html('<h1>Título</h1>', color=False)
        colored = render_html('<h1>Título</h1>', color=True)
        self.assertNotIn("\033", plain)
        self.assertIn("\033", colored)


if __name__ == "__main__":
    unittest.main()
