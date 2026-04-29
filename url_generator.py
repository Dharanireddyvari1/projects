from google_lens_EM import GoogleLensExactMatch

lens = GoogleLensExactMatch()
html = lens.get_exact_match_html("https://i.ebayimg.com/images/g/bRoAAeSwDgxp5kQn/s-l1600.webp")
# writer = open("bodydump.html","w", encoding="utf-8")
# writer.write(html)
# writer.close()