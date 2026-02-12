import json
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from lib.artists import parse_csv_to_dict, sort_artists_by_lastname, extract_image_sources, extract_artist_photos, NAME_COLUMN
from lib.images import get_cached_image_with_rotation, round_corners
from lib.text import load_summaries

pdfmetrics.registerFont(TTFont('Raleway', 'Raleway-VariableFont_wght.ttf'))
pdfmetrics.registerFont(TTFont('Raleway-Bold', 'Raleway-Bold.ttf'))


def scale_image(img, max_width=6*inch, max_height=4*inch):
    """Scale a ReportLab Image while preserving aspect ratio."""
    orig_width = img.imageWidth
    orig_height = img.imageHeight
    aspect = orig_width / orig_height

    if orig_width > max_width:
        new_width = max_width
        new_height = new_width / aspect
        if new_height > max_height:
            new_height = max_height
            new_width = new_height * aspect
    elif orig_height > max_height:
        new_height = max_height
        new_width = new_height * aspect
    else:
        return img

    img.drawWidth = new_width
    img.drawHeight = new_height
    return img


def create_toc(artists_data, artist_photos, styles):
    """Create visual table of contents with artist photos in a grid."""
    toc_elements = []

    title_style = ParagraphStyle(
        'TOCTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1
    )
    toc_elements.append(Paragraph("Artists", title_style))

    name_style = ParagraphStyle(
        'TOCName',
        parent=styles['Normal'],
        fontSize=8,
        alignment=1,
        leading=10,
    )

    grid_data = []
    current_row = []

    for artist in artists_data:
        name = artist[NAME_COLUMN]

        artist_index = artists_data.index(artist)
        target_page = (artist_index // 2) + 3

        cell_contents = []

        if name in artist_photos:
            try:
                image_data = get_cached_image_with_rotation(artist_photos[name][0])
                if image_data:
                    rounded_img_data = round_corners(image_data)
                    img = Image(BytesIO(rounded_img_data))
                    img.drawWidth = 1*inch
                    img.drawHeight = 1*inch

                    linked_image = Table(
                        [[img]],
                        colWidths=[1*inch],
                        rowHeights=[1*inch]
                    )
                    linked_image.hAlign = 'CENTER'
                    cell_contents.append(linked_image)
            except Exception as e:
                print(f"Error processing TOC photo for {name}: {e}")

        cell_contents.append(
            Paragraph(
                f'<a href="#page_{target_page}">{name}</a>',
                name_style
            )
        )

        print(f"TOC: Creating link to page {target_page} for {name}")
        current_row.append(cell_contents)

        if len(current_row) == 5:
            grid_data.append(current_row)
            current_row = []

    if current_row:
        while len(current_row) < 5:
            current_row.append([])
        grid_data.append(current_row)

    grid = Table(
        grid_data,
        colWidths=[1.3*inch]*5,
        style=TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ])
    )

    toc_elements.append(grid)
    toc_elements.append(PageBreak())
    return toc_elements


def create_catalog(artists_data, image_sources, artist_photos):
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []
            self.bg_width, self.bg_height = A4
            self.draw_background()

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()
            self.draw_background()

        def save(self):
            """Add page numbers and footer to each page."""
            print(f"Saving {len(self._saved_page_states)} pages")
            for state in self._saved_page_states:
                page_num = self._pageNumber
                self.bookmarkPage(f'page_{page_num}')
                self.__dict__.update(state)
                self.draw_page_footer()
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def draw_background(self):
            """Draw the background image on the page."""
            self.drawImage(
                'background.jpg',
                0, 0,
                width=self.bg_width,
                height=self.bg_height,
                preserveAspectRatio=False,
                mask=None
            )

        def draw_page_footer(self):
            self.setFont("Raleway", 9)
            self.drawCentredString(A4[0]/2, 0.5*inch, "ESSENTIAL ARTISTS")
            self.drawRightString(A4[0] - 0.5*inch, 0.5*inch, str(self._pageNumber))

    summaries = load_summaries()

    doc = SimpleDocTemplate("ArtistCatalog.pdf",
                          pagesize=A4,
                          leftMargin=inch,
                          rightMargin=inch,
                          topMargin=inch,
                          bottomMargin=inch)

    story = []
    styles = getSampleStyleSheet()

    story.extend(create_toc(artists_data, artist_photos, styles))

    bookmarks = {}

    styles.add(ParagraphStyle(
        name='Links',
        fontSize=12,
        textColor=colors.blue,
        alignment=2,
        fontName='Raleway'
    ))

    styles.add(ParagraphStyle(
        name='Summary',
        fontSize=12,
        leading=11,
        spaceBefore=6,
        spaceAfter=6,
        fontName='Raleway'
    ))

    styles.add(ParagraphStyle(
        name='ArtworkDetails',
        fontSize=10,
        leading=10,
        alignment=1,
        spaceBefore=2,
        spaceAfter=2,
        fontName='Raleway'
    ))

    styles.add(ParagraphStyle(
        name='ArtworkDetailsSide',
        fontSize=12,
        leading=11,
        spaceBefore=0,
        spaceAfter=3,
        fontName='Raleway'
    ))

    artist_name_style = ParagraphStyle(
        'ArtistName',
        fontSize=24,
        fontName='Raleway-Bold',
        spaceBefore=0,
        spaceAfter=6,
        leading=20
    )

    for i in range(0, len(artists_data), 2):
        for j in range(2):
            if i + j >= len(artists_data):
                break

            artist = artists_data[i + j]
            artist_name = artist[NAME_COLUMN]
            print(f"\nProcessing artist: {artist_name}")

            # Create photo cell
            photo_cell = []
            if artist_name in artist_photos:
                try:
                    image_data = get_cached_image_with_rotation(artist_photos[artist_name][0])
                    if image_data:
                        rounded_img_data = round_corners(image_data)
                        img = Image(BytesIO(rounded_img_data))
                        img.drawWidth = 1.5*inch
                        img.drawHeight = 1.5*inch
                        photo_cell.append(img)
                except Exception as e:
                    print(f"Error processing photo: {e}")

            # Create info cell
            info_cell = []
            info_cell.append(Paragraph(artist_name, artist_name_style))

            if artist['Medium']:
                medium = artist['Medium'].replace('[', '').replace(']', '').replace('"', '').replace(',', ', ')
                info_cell.append(Paragraph(f"<i>{medium}</i>", styles['Normal']))

            if artist_name in summaries and summaries[artist_name]:
                info_cell.append(Paragraph(summaries[artist_name], styles['Summary']))

            # Create links cell
            links = []
            if artist.get('Website'):
                links.append(f'<link href="{artist["Website"]}">Website</link>')
            if artist.get('Facebook'):
                links.append(f'<link href="{artist["Facebook"]}">Facebook</link>')
            if artist.get('Instagram'):
                links.append(f'<link href="{artist["Instagram"]}">Instagram</link>')
            if artist.get('Artists (Item)'):
                profile_url = f'https://www.essentialartistsdayton.org{artist["Artists (Item)"]}'
                links.append(f'<link href="{profile_url}">Profile</link>')

            links_cell = []
            if links:
                links_table = Table([[Paragraph("<br/>".join(links), styles['Links'])]],
                                  rowHeights=[img.drawHeight if photo_cell else 1.5*inch])
                links_table.setStyle(TableStyle([
                    ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ]))
                links_cell.append(links_table)

            row_data = [[photo_cell, info_cell, links_cell]]
            artist_row = Table(row_data, colWidths=[1.7*inch, 4*inch, 1.3*inch])
            artist_row.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))

            story.append(artist_row)
            story.append(Spacer(1, 12))

            # Handle artwork row
            if artist_name in image_sources:
                artwork_images = image_sources[artist_name][:4]
                num_artworks = len(artwork_images)
                print(f"Processing {num_artworks} artwork(s) for {artist_name} (limited to first 4)")

                if num_artworks == 1:
                    print(f"Processing single artwork for {artist_name}")
                    try:
                        image_data = get_cached_image_with_rotation(artwork_images[0])
                        if image_data:
                            print(f"Successfully loaded image data for {artist_name}'s artwork")
                            img = Image(BytesIO(image_data))
                            img = scale_image(img, max_width=3.5*inch, max_height=2.4*inch)
                            print(f"Scaled image to {img.drawWidth/inch:.1f}x{img.drawHeight/inch:.1f} inches")

                            details = []
                            if artist.get('Piece Title'):
                                details.append(Paragraph(f"<b>{artist['Piece Title']}</b>",
                                                      styles['ArtworkDetailsSide']))
                                details.append(Spacer(1, 4))
                            if artist.get('Piece Size'):
                                details.append(Paragraph(artist['Piece Size'],
                                                      styles['ArtworkDetailsSide']))
                                details.append(Spacer(1, 4))
                            if artist.get('Piece Medium'):
                                details.append(Paragraph(artist['Piece Medium'],
                                                      styles['ArtworkDetailsSide']))

                            artwork_data = [[None, img, details]]
                            artwork_table = Table(artwork_data,
                                               colWidths=[0.5*inch, 4*inch, 2.2*inch])
                            artwork_table.setStyle(TableStyle([
                                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                                ('ALIGN', (1,0), (1,0), 'RIGHT'),
                                ('LEFTPADDING', (0,0), (-1,-1), 6),
                                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                            ]))
                            story.append(artwork_table)

                        else:
                            print(f"No image data returned for {artist_name}'s artwork")

                    except Exception as e:
                        print(f"Error processing single artwork for {artist_name}:")
                        print(f"  URL: {artwork_images[0]}")
                        print(f"  Error: {str(e)}")

                elif num_artworks >= 2:
                    print(f"Processing multiple artworks for {artist_name}")
                    artwork_row = []
                    for idx, artwork_url in enumerate(artwork_images, 1):
                        print(f"Processing artwork {idx} of {num_artworks}")
                        try:
                            image_data = get_cached_image_with_rotation(artwork_url)
                            if image_data:
                                print(f"Successfully loaded image data for artwork {idx}")
                                img = Image(BytesIO(image_data))

                                if num_artworks == 2:
                                    if idx == 1:
                                        img = scale_image(img, max_width=2.25*inch, max_height=2*inch)
                                    else:
                                        img = scale_image(img, max_width=2.75*inch, max_height=2.5*inch)
                                elif num_artworks == 3:
                                    if idx == 1:
                                        img = scale_image(img, max_width=2*inch, max_height=2*inch)
                                    else:
                                        img = scale_image(img, max_width=2.5*inch, max_height=2.5*inch)
                                else:
                                    if idx == 1:
                                        img = scale_image(img, max_width=1.5*inch, max_height=1.5*inch)
                                    else:
                                        img = scale_image(img, max_width=1.6*inch, max_height=1.75*inch)

                                if idx == 1:
                                    cell_contents = [img]
                                    if artist.get('Piece Title'):
                                        cell_contents.append(Paragraph(artist['Piece Title'],
                                                                    styles['ArtworkDetails']))
                                    if artist.get('Piece Size'):
                                        cell_contents.append(Paragraph(artist['Piece Size'],
                                                                    styles['ArtworkDetails']))
                                    if artist.get('Piece Medium'):
                                        cell_contents.append(Paragraph(artist['Piece Medium'],
                                                                    styles['ArtworkDetails']))
                                else:
                                    cell_contents = [img]

                                artwork_row.append(cell_contents)
                                print(f"Successfully added artwork {idx} to row")

                            else:
                                print(f"No image data returned for artwork {idx}")

                        except Exception as e:
                            print(f"Error processing artwork {idx} for {artist_name}:")
                            print(f"  URL: {artwork_url}")
                            print(f"  Error: {str(e)}")

                    if artwork_row:
                        print(f"Creating table with {len(artwork_row)} processed artworks")
                        col_width = 6.5*inch / len(artwork_row)
                        artwork_table = Table([artwork_row], colWidths=[col_width]*len(artwork_row))
                        artwork_table.setStyle(TableStyle([
                            ('VALIGN', (0,0), (-1,-1), 'TOP'),
                            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                            ('LEFTPADDING', (0,0), (-1,-1), 6),
                            ('RIGHTPADDING', (0,0), (-1,-1), 6),
                        ]))
                        story.append(artwork_table)
                    else:
                        print(f"WARNING: No artwork images were successfully processed for {artist_name}")
            else:
                print(f"No artwork sources found for {artist_name}")

            if j == 0:
                story.append(Spacer(1, 36))

        story.append(PageBreak())

    def make_canvas(filename, **kwargs):
        return NumberedCanvas(filename, bookmarks=bookmarks, **kwargs)

    print("\nBuilding PDF document...")
    doc.build(story, canvasmaker=make_canvas)
    print("PDF document completed")


if __name__ == "__main__":
    csv_data = parse_csv_to_dict('Artists.csv')
    if csv_data:
        csv_data = sort_artists_by_lastname(csv_data)
        image_sources = extract_image_sources(csv_data)
        artist_photos = extract_artist_photos(csv_data)
        create_catalog(csv_data, image_sources, artist_photos)
