# Music Catalog Metadata Pipeline

This project ingests Spotify, YouTube, and MusicBrainz metadata, retains raw API
responses in MongoDB, and builds a normalized PostgreSQL catalog for reporting.

The data-quality controls and scalable warehouse design are documented in
[docs/data-quality-and-storage.md](docs/data-quality-and-storage.md).
