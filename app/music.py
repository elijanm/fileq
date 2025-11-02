import os
import random
from pathlib import Path
from typing import Dict, List
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MusicDirectoryGenerator:
    def __init__(self):
        # Sample data for realistic music library
        self.artists = {
            "Rock": [
                "The Beatles", "Led Zeppelin", "Pink Floyd", "Queen", "The Rolling Stones",
                "AC/DC", "Metallica", "Nirvana", "Foo Fighters", "Red Hot Chili Peppers"
            ],
            "Pop": [
                "Taylor Swift", "Ed Sheeran", "Adele", "Bruno Mars", "Ariana Grande",
                "The Weeknd", "Billie Eilish", "Dua Lipa", "Harry Styles", "Olivia Rodrigo"
            ],
            "Hip-Hop": [
                "Kendrick Lamar", "Drake", "J. Cole", "Kanye West", "Jay-Z",
                "Eminem", "Travis Scott", "Future", "Lil Wayne", "Nas"
            ],
            "Electronic": [
                "Daft Punk", "Deadmau5", "Calvin Harris", "Skrillex", "The Chainsmokers",
                "Marshmello", "David Guetta", "Tiësto", "Martin Garrix", "Zedd"
            ],
            "Jazz": [
                "Miles Davis", "John Coltrane", "Duke Ellington", "Billie Holiday", "Ella Fitzgerald",
                "Louis Armstrong", "Charlie Parker", "Thelonious Monk", "Bill Evans", "Herbie Hancock"
            ],
            "Classical": [
                "Ludwig van Beethoven", "Wolfgang Amadeus Mozart", "Johann Sebastian Bach",
                "Frédéric Chopin", "Pyotr Ilyich Tchaikovsky", "Claude Debussy",
                "Johannes Brahms", "Antonio Vivaldi", "Franz Schubert", "Igor Stravinsky"
            ]
        }
        
        self.album_templates = {
            "Rock": [
                "Greatest Hits", "Live at {venue}", "Unplugged", "The Collection", "Best Of",
                "Rock Anthems", "Thunder & Lightning", "Electric Dreams", "Wild Nights", "Power Ballads"
            ],
            "Pop": [
                "Pop Perfection", "Chart Toppers", "Golden Hits", "Sweet Melodies", "Radio Favorites",
                "Dance Floor", "Love Songs", "Summer Vibes", "Midnight Sessions", "Pure Pop"
            ],
            "Hip-Hop": [
                "Street Chronicles", "Beats & Rhymes", "Underground", "City Lights", "Raw Talent",
                "Freestyle Sessions", "The Come Up", "Block Party", "Mic Check", "Flow State"
            ],
            "Electronic": [
                "Synth Dreams", "Digital Waves", "Bass Drop", "Electric Pulse", "Neon Nights",
                "Circuit Breaker", "Voltage", "Binary Beats", "Cyber Sound", "Frequency"
            ],
            "Jazz": [
                "Blue Note Sessions", "Smooth Jazz", "Late Night Jazz", "Bebop Chronicles", "Cool Jazz",
                "Jazz Standards", "Improvisation", "Swing Time", "Modal Jazz", "Fusion"
            ],
            "Classical": [
                "Symphony Collection", "Piano Works", "Chamber Music", "Concertos", "Sonatas",
                "Orchestral Works", "String Quartets", "Requiem", "Variations", "Masterpieces"
            ]
        }
        
        self.song_templates = {
            "Rock": [
                "Thunder Road", "Midnight Train", "Electric Fire", "Breaking Chains", "Wild Heart",
                "Rock & Roll Soul", "Highway Blues", "Rebel Yell", "Power Surge", "Stone Cold"
            ],
            "Pop": [
                "Dancing Queen", "Love Story", "Perfect Match", "Golden Hour", "Sweet Dreams",
                "Starlight", "Rainbow", "Butterfly", "Sunrise", "Forever Young"
            ],
            "Hip-Hop": [
                "Street Wisdom", "Money Talks", "Hustle Hard", "Real Talk", "City Life",
                "Flow Check", "Bars & Beats", "Underground King", "Mic Drop", "Crown"
            ],
            "Electronic": [
                "Digital Love", "Neon Lights", "Bass Line", "Voltage Drop", "Cyber Dreams",
                "Circuit Board", "Electric Feel", "Pulse", "Frequency", "Matrix"
            ],
            "Jazz": [
                "Blue Moon", "Smooth Operator", "Night Train", "Cool Breeze", "Velvet Voice",
                "Saxophone Serenade", "Piano Blues", "Midnight Jazz", "Swing Low", "Bebop"
            ],
            "Classical": [
                "Allegro", "Andante", "Adagio", "Prelude", "Etude",
                "Nocturne", "Waltz", "Minuet", "Rondo", "Finale"
            ]
        }
        
        self.years = list(range(1960, 2025))
        self.file_extensions = ['.mp3', '.flac', '.wav', '.m4a']
        self.file_sizes_mb = [3, 4, 5, 6, 7, 8, 10, 12, 15]  # Realistic song file sizes
        
    def generate_music_library(self, base_folder: str = "music_library", 
                             artists_per_genre: int = 3, 
                             albums_per_artist: int = 2,
                             songs_per_album: int = 8,
                             create_files: bool = True):
        """Generate a complete music library directory structure."""
        base_path = Path(base_folder)
        base_path.mkdir(exist_ok=True)
        
        logger.info(f"🎵 Generating music library in '{base_folder}'...")
        
        total_files = 0
        
        for genre, artist_list in self.artists.items():
            genre_path = base_path / genre
            genre_path.mkdir(exist_ok=True)
            logger.info(f"📁 Creating genre: {genre}")
            
            # Select random artists from this genre
            selected_artists = random.sample(artist_list, min(artists_per_genre, len(artist_list)))
            
            for artist in selected_artists:
                artist_path = genre_path / artist
                artist_path.mkdir(exist_ok=True)
                
                # Generate albums for this artist
                for album_idx in range(albums_per_artist):
                    year = random.choice(self.years)
                    album_name = random.choice(self.album_templates[genre])
                    
                    # Create unique album name
                    if "{venue}" in album_name:
                        venues = ["Madison Square Garden", "Wembley", "Red Rocks", "Hollywood Bowl"]
                        album_name = album_name.format(venue=random.choice(venues))
                    
                    album_folder = f"({year}) {album_name}"
                    album_path = artist_path / album_folder
                    album_path.mkdir(exist_ok=True)
                    
                    logger.info(f"  💿 Album: {artist} - {album_name} ({year})")
                    
                    # Generate songs for this album
                    selected_songs = random.sample(
                        self.song_templates[genre], 
                        min(songs_per_album, len(self.song_templates[genre]))
                    )
                    
                    for song_idx, song_name in enumerate(selected_songs, 1):
                        # Create song filename with track number
                        extension = random.choice(self.file_extensions)
                        filename = f"{song_idx:02d}. {song_name}{extension}"
                        file_path = album_path / filename
                        
                        if create_files:
                            self._create_music_file(file_path)
                        else:
                            # Just create empty file
                            file_path.touch()
                        
                        total_files += 1
        
        logger.info(f"✅ Generated music library with {total_files} songs")
        logger.info(f"📊 Structure: {len(self.artists)} genres, {artists_per_genre} artists per genre")
        logger.info(f"📊 {albums_per_artist} albums per artist, {songs_per_album} songs per album")
        
        return base_path
    
    def _create_music_file(self, file_path: Path, chunk_size: int = 1024 * 1024):
        """Create a binary file that simulates a music file."""
        size_mb = random.choice(self.file_sizes_mb)
        size_bytes = size_mb * 1024 * 1024
        
        with open(file_path, "wb") as f:
            remaining = size_bytes
            while remaining > 0:
                current_chunk = min(chunk_size, remaining)
                f.write(os.urandom(current_chunk))
                remaining -= current_chunk
    
    def generate_playlist_structure(self, base_folder: str = "playlists"):
        """Generate playlist folders with symbolic structure."""
        playlists = [
            "Workout Mix", "Chill Vibes", "Road Trip", "Study Music", "Party Hits",
            "90s Nostalgia", "Acoustic Sessions", "Summer 2024", "Rainy Day", "Focus Flow"
        ]
        
        base_path = Path(base_folder)
        base_path.mkdir(exist_ok=True)
        
        for playlist in playlists:
            playlist_path = base_path / playlist
            playlist_path.mkdir(exist_ok=True)
            
            # Create a simple text file listing songs (simulation)
            playlist_file = playlist_path / f"{playlist}.m3u"
            with open(playlist_file, "w") as f:
                f.write(f"# Playlist: {playlist}\n")
                f.write("# Generated playlist file\n")
        
        logger.info(f"🎵 Generated {len(playlists)} playlist folders")
    
    def print_structure_summary(self, base_folder: str = "music_library"):
        """Print a summary of the generated structure."""
        base_path = Path(base_folder)
        if not base_path.exists():
            logger.error(f"Folder '{base_folder}' does not exist")
            return
        
        print(f"\n📁 Music Library Structure Summary:")
        print(f"📍 Base folder: {base_path.absolute()}")
        print("=" * 60)
        
        total_files = 0
        total_size_mb = 0
        
        for genre_path in sorted(base_path.iterdir()):
            if genre_path.is_dir():
                print(f"\n🎵 {genre_path.name}/")
                
                for artist_path in sorted(genre_path.iterdir()):
                    if artist_path.is_dir():
                        print(f"  👨‍🎤 {artist_path.name}/")
                        
                        for album_path in sorted(artist_path.iterdir()):
                            if album_path.is_dir():
                                songs = list(album_path.glob("*.*"))
                                total_files += len(songs)
                                
                                # Calculate folder size
                                folder_size = sum(f.stat().st_size for f in songs if f.is_file())
                                folder_size_mb = folder_size / (1024 * 1024)
                                total_size_mb += folder_size_mb
                                
                                print(f"    💿 {album_path.name}/ ({len(songs)} songs, {folder_size_mb:.1f} MB)")
        
        print("=" * 60)
        print(f"📊 Total: {total_files} songs, {total_size_mb:.1f} MB")


# Usage example
def main():
    """Main function to demonstrate the music directory generator."""
    generator = MusicDirectoryGenerator()
    
    # Generate full music library
    generator.generate_music_library(
        base_folder="music_library",
        artists_per_genre=2,      # 2 artists per genre
        albums_per_artist=2,      # 2 albums per artist  
        songs_per_album=6,        # 6 songs per album
        create_files=True         # Create actual binary files
    )
    
    # Generate playlist structure
    generator.generate_playlist_structure("playlists")
    
    # Print summary
    generator.print_structure_summary("music_library")


if __name__ == "__main__":
    main()