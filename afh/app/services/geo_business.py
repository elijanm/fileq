import requests
import csv
import time
from datetime import datetime, date
import re
from typing import List, Dict, Optional
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import json
import os

class UsageTracker:
    """
    Track API usage across sessions to stay within free tiers
    Saves to a JSON file to persist across runs
    
    Free Tier Limits:
    - Google Places API: 10,000 calls/month (Essentials tier)
    - TomTom: 50,000 calls/day
    - Mapbox: 100,000 calls/month
    """
    
    def __init__(self, tracking_file='api_usage.json'):
        self.tracking_file = tracking_file
        self.usage = self._load_usage()
        
        # Free tier limits
        self.limits = {
            'google': {'limit': 10000, 'period': 'month'},
            'tomtom': {'limit': 50000, 'period': 'day'},
            'mapbox': {'limit': 100000, 'period': 'month'}
        }
    
    def _load_usage(self):
        """Load usage data from file"""
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'google': {'count': 0, 'date': str(date.today())},
            'tomtom': {'count': 0, 'date': str(date.today())},
            'mapbox': {'count': 0, 'date': str(date.today())}
        }
    
    def _save_usage(self):
        """Save usage data to file"""
        with open(self.tracking_file, 'w') as f:
            json.dump(self.usage, f, indent=2)
    
    def _reset_if_needed(self, api):
        """Reset counter if period has expired"""
        period = self.limits[api]['period']
        last_date = self.usage[api]['date']
        current_date = str(date.today())
        
        if period == 'day' and last_date != current_date:
            self.usage[api] = {'count': 0, 'date': current_date}
        elif period == 'month':
            last_month = last_date[:7]  # YYYY-MM
            current_month = current_date[:7]
            if last_month != current_month:
                self.usage[api] = {'count': 0, 'date': current_date}
    
    def can_use(self, api, count=1):
        """Check if we can make API calls within free tier"""
        self._reset_if_needed(api)
        current = self.usage[api]['count']
        limit = self.limits[api]['limit']
        return (current + count) <= limit
    
    def record_usage(self, api, count=1):
        """Record API usage"""
        self._reset_if_needed(api)
        self.usage[api]['count'] += count
        self._save_usage()
    
    def get_remaining(self, api):
        """Get remaining free tier calls"""
        self._reset_if_needed(api)
        current = self.usage[api]['count']
        limit = self.limits[api]['limit']
        return max(0, limit - current)
    
    def get_status(self):
        """Get status of all APIs"""
        status = {}
        for api in ['google', 'tomtom', 'mapbox']:
            remaining = self.get_remaining(api)
            limit = self.limits[api]['limit']
            period = self.limits[api]['period']
            status[api] = {
                'remaining': remaining,
                'limit': limit,
                'period': period,
                'used': limit - remaining
            }
        return status


class GoogleMapsScraperPlaywright:
    """
    Google Maps scraper using Playwright
    WARNING: Violates Google's Terms of Service - use as fallback only
    """
    
    def __init__(self, headless=True, slow_mo=0):
        self.headless = headless
        self.slow_mo = slow_mo  # Milliseconds to slow down operations
        self.browser = None
        self.context = None
        self.page = None
        
    async def init_browser(self):
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,  # Slow down for better reliability
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox',
                '--start-maximized'  # Start maximized for better visibility
            ]
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = await self.context.new_page()
        
        # Set longer default timeout
        self.page.set_default_timeout(90000)  # 90 seconds
        
        # Enable console logging to see what's happening
        self.page.on("console", lambda msg: print(f"  🖥️  Browser: {msg.text}"))
        
    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
    async def scrape_google_maps(self, search_query, location, max_results=100):
        """Scrape Google Maps search results with infinite scroll and images"""
        if not self.page:
            await self.init_browser()
        
        businesses = []
        
        import urllib.parse
        encoded_query = urllib.parse.quote(f"{search_query} in {location}")
        search_url = f"https://www.google.com/maps/search/{encoded_query}"
        
        try:
            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(5)
            
            await self.page.wait_for_selector('div.Nv2PK', timeout=20000)
            
            # Infinite scroll
            results_panel = await self.page.query_selector('div[role="feed"]')
            
            if results_panel:
                previous_count = 0
                no_new_results_count = 0
                scroll_attempts = 0
                max_scroll_attempts = 30
                
                while scroll_attempts < max_scroll_attempts:
                    await results_panel.evaluate('el => el.scrollTop = el.scrollHeight')
                    await asyncio.sleep(2)
                    
                    business_cards = await self.page.query_selector_all('div.Nv2PK')
                    current_count = len(business_cards)
                    
                    if current_count == previous_count:
                        no_new_results_count += 1
                        if no_new_results_count >= 3:
                            break
                    else:
                        no_new_results_count = 0
                    
                    previous_count = current_count
                    scroll_attempts += 1
                    
                    if current_count >= max_results * 2:
                        break
            
            business_cards = await self.page.query_selector_all('div.Nv2PK')
            
            scraped_names = set()
            successful_details = 0
            failed_details = 0
            
            for idx in range(len(business_cards)):
                if len(businesses) >= max_results:
                    break
                
                try:
                    # CRITICAL: Navigate back to search results before each iteration
                    if idx > 0:  # Skip for first item
                        await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(2)
                        
                        # Wait for results to reload
                        await self.page.wait_for_selector('div.Nv2PK', timeout=10000)
                        await asyncio.sleep(1)
                    
                    # Re-query cards after navigation
                    business_cards = await self.page.query_selector_all('div.Nv2PK')
                    if idx >= len(business_cards):
                        break
                    
                    card = business_cards[idx]
                    
                    name_el = await card.query_selector('div.qBF1Pd, div.fontHeadlineSmall')
                    if not name_el:
                        continue
                    
                    name = (await name_el.inner_text()).strip()
                    
                    # Skip aggregators
                    if ' - Adult Family Homes' in name or 'directory' in name.lower():
                        continue
                    
                    if name in scraped_names:
                        continue
                    
                    # Get basic card data
                    image_url = ''
                    rating = ''
                    reviews_count = ''
                    
                    try:
                        img_el = await card.query_selector('img.DaSXdd, img.loaded')
                        if img_el:
                            img_src = await img_el.get_attribute('src')
                            if img_src and img_src.startswith('http'):
                                image_url = img_src
                    except:
                        pass
                    
                    try:
                        rating_el = await card.query_selector('span.MW4etd')
                        if rating_el:
                            rating = (await rating_el.inner_text()).strip()
                    except:
                        pass
                    
                    try:
                        reviews_el = await card.query_selector('span.UY7F9')
                        if reviews_el:
                            reviews_text = await reviews_el.inner_text()
                            reviews_count = re.sub(r'[^\d]', '', reviews_text)
                    except:
                        pass
                    
                    # Click to get details
                    link = await card.query_selector('a.hfpxzc')
                    if link:
                        # Scroll card into view
                        await card.evaluate('el => el.scrollIntoView({block: "center", behavior: "smooth"})')
                        await asyncio.sleep(0.5)
                        
                        old_url = self.page.url
                        
                        try:
                            # Force click
                            await link.click(force=True)
                            
                            # Wait for URL to change
                            url_changed = False
                            for _ in range(10):
                                await asyncio.sleep(0.5)
                                if self.page.url != old_url:
                                    url_changed = True
                                    break
                            
                            if url_changed:
                                # Wait for details to load
                                await asyncio.sleep(2)
                                
                                # Extract details
                                details = await self._extract_business_details()
                                
                                if details:
                                    business_data = details
                                    business_data['city'] = location
                                    business_data['source'] = 'Google Maps (Scraped)'
                                    business_data['data_method'] = 'scraper'
                                    
                                    # Use card data as fallback
                                    if not business_data.get('rating'):
                                        business_data['rating'] = rating
                                    if not business_data.get('reviews_count'):
                                        business_data['reviews_count'] = reviews_count
                                    if not business_data.get('image_url'):
                                        business_data['image_url'] = image_url
                                    
                                    successful_details += 1
                                else:
                                    # Fallback to card data
                                    business_data = self._create_card_only_entry(name, location, image_url, rating, reviews_count)
                                    failed_details += 1
                            else:
                                # Click failed
                                business_data = self._create_card_only_entry(name, location, image_url, rating, reviews_count)
                                failed_details += 1
                        
                        except Exception as e:
                            business_data = self._create_card_only_entry(name, location, image_url, rating, reviews_count)
                            failed_details += 1
                    else:
                        # No link
                        business_data = self._create_card_only_entry(name, location, image_url, rating, reviews_count)
                        failed_details += 1
                    
                    scraped_names.add(name)
                    businesses.append(business_data)
                    
                    print(f"  ✅ {len(businesses)}: {name} - {'Details' if successful_details > failed_details else 'Card only'}")
                    
                except Exception as e:
                    print(f"  ❌ Error on {idx}: {str(e)[:50]}")
                    continue
            
            print(f"\n  ✅ Total: {len(businesses)} | Details: {successful_details} | Card only: {failed_details}")
            
        except Exception as e:
            print(f"    Scraping error: {str(e)[:100]}")
        
        return businesses

    def _create_card_only_entry(self, name, location, image_url, rating, reviews_count):
        """Create entry with only card data when details extraction fails"""
        return {
            'name': name,
            'city': location,
            'source': 'Google Maps (Scraped - Card Only)',
            'data_method': 'scraper',
            'image_url': image_url,
            'address': '',
            'phone': '',
            'website': '',
            'email': '',
            'category': '',
            'latitude': '',
            'longitude': '',
            'rating': rating,
            'reviews_count': reviews_count,
            'price_level': '',
            'hours': '',
            'google_maps_url': ''
        }
    async def _extract_business_details(self):
        """Extract comprehensive business information including image"""
        try:
            await self.page.wait_for_selector('div.fontHeadlineSmall, h1', timeout=4000)
        except:
            return None
        
        try:
            data = {}
            
            # Name
            name_selectors = ['div.fontHeadlineSmall', 'h1.DUwDvf', 'div.qBF1Pd', 'h1']
            name_el = None
            for selector in name_selectors:
                name_el = await self.page.query_selector(selector)
                if name_el:
                    break
            
            if name_el:
                data['name'] = (await name_el.inner_text()).strip()
            else:
                return None
            
            # Image - try multiple selectors for the main business photo
            data['image_url'] = ''
            try:
                # Try main hero image first
                img_selectors = [
                    'button[aria-label*="Photo"] img',  # Hero image button
                    'img.DaSXdd',  # Card images
                    'div.RZ66Rb img',  # Another common selector
                    'img[src*="googleusercontent"]'  # Any Google-hosted image
                ]
                
                for selector in img_selectors:
                    img_el = await self.page.query_selector(selector)
                    if img_el:
                        img_src = await img_el.get_attribute('src')
                        if img_src and 'googleusercontent' in img_src:
                            # Clean up the URL to get high-res version
                            # Google URLs often have size parameters like =w100-h100
                            # Change to larger size like =w800-h600
                            if '=w' in img_src:
                                img_src = re.sub(r'=w\d+-h\d+', '=w800-h600', img_src)
                            data['image_url'] = img_src
                            break
            except:
                pass
            
            # Rating
            try:
                rating_el = await self.page.query_selector('span.MW4etd')
                data['rating'] = (await rating_el.inner_text()).strip() if rating_el else ''
            except:
                data['rating'] = ''
            
            # Reviews count
            try:
                reviews_el = await self.page.query_selector('span.UY7F9')
                if reviews_el:
                    reviews_text = await reviews_el.inner_text()
                    data['reviews_count'] = re.sub(r'[^\d]', '', reviews_text)
                else:
                    data['reviews_count'] = ''
            except:
                data['reviews_count'] = ''
            
            # Address
            try:
                data['address'] = ''
                w4_divs = await self.page.query_selector_all('div.W4Efsd')
                for div in w4_divs:
                    text = await div.inner_text()
                    if any(x in text for x in ['St', 'Ave', 'Rd', 'Blvd', 'Dr', 'Ln']) and any(c.isdigit() for c in text):
                        data['address'] = text.split('\n')[0].strip()
                        break
            except:
                data['address'] = ''
            
            # Phone
            try:
                phone_el = await self.page.query_selector('span.UsdlK')
                data['phone'] = (await phone_el.inner_text()).strip() if phone_el else ''
            except:
                data['phone'] = ''
            
            # Website
            try:
                website_el = await self.page.query_selector('a[data-value="Website"]')
                data['website'] = await website_el.get_attribute('href') if website_el else ''
            except:
                data['website'] = ''
            
            # Category
            try:
                data['category'] = ''
                w4_divs = await self.page.query_selector_all('div.W4Efsd span')
                for span in w4_divs[:3]:
                    text = await span.inner_text()
                    if 5 < len(text) < 50 and not any(x in text for x in ['St', 'Ave', '·', '(', 'Open', 'Closed']):
                        data['category'] = text.strip()
                        break
            except:
                data['category'] = ''
            
            data['hours'] = ''
            data['price_level'] = ''
            
            # URL and coordinates
            data['google_maps_url'] = self.page.url
            coords = self._extract_coordinates_from_url(self.page.url)
            data['latitude'] = coords[0] if coords else ''
            data['longitude'] = coords[1] if coords else ''
            
            return data
            
        except Exception as e:
            return None
    async def _extract_business_details_dep(self):
        """Extract comprehensive business information"""
        try:
            # Wait for details panel to load
            try:
                await self.page.wait_for_selector('div.fontHeadlineSmall, h1', timeout=4000)
            except:
                return None
            
            data = {}
            
            # Name - try multiple selectors
            try:
                name_selectors = [
                    'div.fontHeadlineSmall',
                    'h1.DUwDvf',
                    'div.qBF1Pd',
                    'h1'
                ]
                name_el = None
                for selector in name_selectors:
                    name_el = await self.page.query_selector(selector)
                    if name_el:
                        break
                
                if name_el:
                    data['name'] = (await name_el.inner_text()).strip()
                else:
                    return None
            except:
                return None
            
            # Rating
            try:
                rating_el = await self.page.query_selector('span.MW4etd')
                data['rating'] = (await rating_el.inner_text()).strip() if rating_el else ''
            except:
                data['rating'] = ''
            
            # Reviews count
            try:
                reviews_el = await self.page.query_selector('span.UY7F9')
                if reviews_el:
                    reviews_text = await reviews_el.inner_text()
                    data['reviews_count'] = re.sub(r'[^\d]', '', reviews_text)
                else:
                    data['reviews_count'] = ''
            except:
                data['reviews_count'] = ''
            
            # Address - look in all W4Efsd divs
            try:
                data['address'] = ''
                w4_divs = await self.page.query_selector_all('div.W4Efsd')
                for div in w4_divs:
                    text = await div.inner_text()
                    if any(x in text for x in ['St', 'Ave', 'Rd', 'Blvd', 'Dr', 'Ln']) and any(c.isdigit() for c in text):
                        data['address'] = text.split('\n')[0].strip()
                        break
            except:
                data['address'] = ''
            
            # Phone
            try:
                phone_el = await self.page.query_selector('span.UsdlK')
                data['phone'] = (await phone_el.inner_text()).strip() if phone_el else ''
            except:
                data['phone'] = ''
            
            # Website
            try:
                website_el = await self.page.query_selector('a[data-value="Website"]')
                data['website'] = await website_el.get_attribute('href') if website_el else ''
            except:
                data['website'] = ''
            
            # Category
            try:
                data['category'] = ''
                w4_divs = await self.page.query_selector_all('div.W4Efsd span')
                for span in w4_divs[:3]:
                    text = await span.inner_text()
                    if 5 < len(text) < 50 and not any(x in text for x in ['St', 'Ave', '·', '(', 'Open', 'Closed']):
                        data['category'] = text.strip()
                        break
            except:
                data['category'] = ''
            
            # Hours, email, coordinates, etc.
            data['hours'] = ''
            data['email'] = ''
            data['amenities'] = ''
            data['price_level'] = ''
            data['plus_code'] = ''
            data['place_id'] = ''
            
            # URL and coordinates
            data['google_maps_url'] = self.page.url
            coords = self._extract_coordinates_from_url(self.page.url)
            data['latitude'] = coords[0] if coords else ''
            data['longitude'] = coords[1] if coords else ''
            
            return data
            
        except Exception as e:
            return None
    async def _extract_business_details_old(self):
        """Extract detailed information from business page"""
        try:
            data = {}
            
            # Name
            try:
                name_el = await self.page.wait_for_selector('h1.DUwDvf', timeout=3000)
                data['name'] = await name_el.inner_text()
            except:
                data['name'] = 'Unknown'
            
            # Rating
            try:
                rating_el = await self.page.query_selector('span.MW4etd')
                data['rating'] = await rating_el.inner_text() if rating_el else ''
            except:
                data['rating'] = ''
            
            # Reviews count
            try:
                reviews_el = await self.page.query_selector('span.UY7F9')
                if reviews_el:
                    reviews_text = await reviews_el.inner_text()
                    data['reviews_count'] = re.sub(r'[^\d]', '', reviews_text)
                else:
                    data['reviews_count'] = ''
            except:
                data['reviews_count'] = ''
            
            # Category
            try:
                category_el = await self.page.query_selector('button.DkEaL')
                data['category'] = await category_el.inner_text() if category_el else ''
            except:
                data['category'] = ''
            
            # Address
            try:
                address_el = await self.page.query_selector('button[data-item-id="address"]')
                if address_el:
                    aria_label = await address_el.get_attribute('aria-label')
                    data['address'] = aria_label.replace('Address: ', '') if aria_label else ''
                else:
                    data['address'] = ''
            except:
                data['address'] = ''
            
            # Phone
            try:
                phone_el = await self.page.query_selector('button[data-item-id^="phone:tel:"]')
                if phone_el:
                    phone_aria = await phone_el.get_attribute('aria-label')
                    data['phone'] = phone_aria.replace('Phone: ', '') if phone_aria else ''
                else:
                    data['phone'] = ''
            except:
                data['phone'] = ''
            
            # Website
            try:
                website_el = await self.page.query_selector('a[data-item-id="authority"]')
                data['website'] = await website_el.get_attribute('href') if website_el else ''
            except:
                data['website'] = ''
            
            # Hours
            try:
                hours_el = await self.page.query_selector('button[data-item-id="oh"]')
                if hours_el:
                    hours_aria = await hours_el.get_attribute('aria-label')
                    data['hours'] = hours_aria if hours_aria else ''
                else:
                    data['hours'] = ''
            except:
                data['hours'] = ''
            
            # Price level
            try:
                price_el = await self.page.query_selector('span.mgr77e')
                if price_el:
                    price_text = await price_el.inner_text()
                    data['price_level'] = len(price_text.strip())
                else:
                    data['price_level'] = ''
            except:
                data['price_level'] = ''
            
            # Google Maps URL & Coordinates
            data['google_maps_url'] = self.page.url
            coords = self._extract_coordinates_from_url(self.page.url)
            data['latitude'] = coords[0] if coords else ''
            data['longitude'] = coords[1] if coords else ''
            
            return data
            
        except Exception as e:
            return None
    async def _extract_business_details(self):
        """Extract comprehensive business information"""
        # Wait for the details panel to actually load
        try:
            await self.page.wait_for_selector('h1.fontHeadlineSmall, div.qBF1Pd', timeout=5000)
        except:
            print(f"    ⚠️  Details panel didn't load")
            return None
        
        
        try:
            data = {}
            
            # Name
            try:
                name_el = await self.page.wait_for_selector('h1.fontHeadlineSmall, div.qBF1Pd', timeout=3000)
                data['name'] = (await name_el.inner_text()).strip()
            except:
                data['name'] = 'Unknown'
            
            # Rating
            try:
                rating_el = await self.page.query_selector('span.MW4etd')
                data['rating'] = (await rating_el.inner_text()).strip() if rating_el else ''
            except:
                data['rating'] = ''
            
            # Reviews count
            try:
                reviews_el = await self.page.query_selector('span.UY7F9')
                if reviews_el:
                    reviews_text = await reviews_el.inner_text()
                    data['reviews_count'] = re.sub(r'[^\d]', '', reviews_text)
                else:
                    data['reviews_count'] = ''
            except:
                data['reviews_count'] = ''
            
            # Category
            try:
                # Look for category in W4Efsd divs
                w4_divs = await self.page.query_selector_all('div.W4Efsd')
                for div in w4_divs:
                    text = await div.inner_text()
                    # Categories are usually short and don't contain street addresses
                    if 5 < len(text) < 60 and not any(x in text for x in ['St', 'Ave', 'Rd', 'Blvd', 'Open', 'Closed', '·', '(']):
                        data['category'] = text.strip()
                        break
                if 'category' not in data:
                    data['category'] = ''
            except:
                data['category'] = ''
            
            # Address
            try:
                address_found = False
                # Look through W4Efsd divs for address
                w4_divs = await self.page.query_selector_all('div.W4Efsd')
                for div in w4_divs:
                    text = await div.inner_text()
                    # Addresses contain street indicators and numbers
                    if any(x in text for x in ['St', 'Ave', 'Rd', 'Blvd', 'Dr', 'Ln', 'Pl', 'Way']) and any(c.isdigit() for c in text):
                        lines = text.split('\n')
                        data['address'] = lines[0].strip()
                        address_found = True
                        break
                if not address_found:
                    data['address'] = ''
            except:
                data['address'] = ''
            
            # Phone
            try:
                phone_el = await self.page.query_selector('span.UsdlK')
                if phone_el:
                    phone_text = await phone_el.inner_text()
                    data['phone'] = phone_text.strip()
                else:
                    data['phone'] = ''
            except:
                data['phone'] = ''
            
            # Website
            try:
                website_el = await self.page.query_selector('a.lcr4fd[data-value="Website"]')
                if website_el:
                    data['website'] = await website_el.get_attribute('href')
                else:
                    data['website'] = ''
            except:
                data['website'] = ''
            
            # Email (extract from website or page content)
            try:
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                page_content = await self.page.content()
                emails = re.findall(email_pattern, page_content)
                # Filter out common false positives
                valid_emails = [e for e in emails if not any(x in e.lower() for x in ['example.com', 'test.com', 'google.com', 'gstatic.com'])]
                data['email'] = valid_emails[0] if valid_emails else ''
            except:
                data['email'] = ''
            
            # Business Hours
            try:
                hours_data = []
                # Try to click hours button to expand
                hours_button = await self.page.query_selector('button[data-item-id="oh"]')
                if hours_button:
                    try:
                        await hours_button.click()
                        await asyncio.sleep(0.5)
                        
                        # Get expanded hours
                        hours_table = await self.page.query_selector('table.eK4R0e')
                        if hours_table:
                            rows = await hours_table.query_selector_all('tr')
                            for row in rows:
                                day_el = await row.query_selector('td.ylH6lf')
                                time_el = await row.query_selector('td.mxowUb')
                                if day_el and time_el:
                                    day = await day_el.inner_text()
                                    time = await time_el.inner_text()
                                    hours_data.append(f"{day}: {time}")
                        
                        # Close the hours panel
                        await hours_button.click()
                        await asyncio.sleep(0.3)
                    except:
                        pass
                
                data['hours'] = ' | '.join(hours_data) if hours_data else ''
            except:
                data['hours'] = ''
            
            # Plus Code (alternative to coordinates)
            try:
                plus_code_el = await self.page.query_selector('button[data-item-id="oloc"]')
                if plus_code_el:
                    plus_code_text = await plus_code_el.get_attribute('aria-label')
                    data['plus_code'] = plus_code_text.replace('Plus code: ', '').strip() if plus_code_text else ''
                else:
                    data['plus_code'] = ''
            except:
                data['plus_code'] = ''
            
            # Amenities/Features
            try:
                amenities = []
                # Look for accessibility and other features
                feature_buttons = await self.page.query_selector_all('button[aria-label*="Wheelchair"], button[aria-label*="accessible"]')
                for btn in feature_buttons[:5]:  # Limit to first 5
                    label = await btn.get_attribute('aria-label')
                    if label:
                        amenities.append(label.strip())
                data['amenities'] = ', '.join(amenities) if amenities else ''
            except:
                data['amenities'] = ''
            
            # Price Level
            try:
                price_el = await self.page.query_selector('span.mgr77e')
                if price_el:
                    price_text = await price_el.inner_text()
                    data['price_level'] = len(price_text.strip())
                else:
                    data['price_level'] = ''
            except:
                data['price_level'] = ''
            
            # Google Maps URL & Coordinates
            data['google_maps_url'] = self.page.url
            coords = self._extract_coordinates_from_url(self.page.url)
            data['latitude'] = coords[0] if coords else ''
            data['longitude'] = coords[1] if coords else ''
            
            # Place ID (from URL)
            try:
                place_id_match = re.search(r'!1s([^!]+)!', self.page.url)
                data['place_id'] = place_id_match.group(1) if place_id_match else ''
            except:
                data['place_id'] = ''
            
            return data
            
        except Exception as e:
            print(f"    ⚠️  Extraction error: {str(e)[:100]}")
            return None
    def _extract_coordinates_from_url(self, url):
        """Extract lat/lng from Google Maps URL"""
        try:
            pattern = r'@(-?\d+\.\d+),(-?\d+\.\d+)'
            match = re.search(pattern, url)
            if match:
                return (float(match.group(1)), float(match.group(2)))
        except:
            pass
        return None


class SmartHybridExtractor:
    """
    Smart Hybrid Extractor that:
    1. Uses ALL free tiers first (Google 10k, TomTom 50k, Mapbox 100k)
    2. Falls back to scraping when free tiers exhausted
    3. Falls back to scraping if API keys not provided
    4. Optimizes cost by selecting cheapest available API
    """
    
    def __init__(self, tomtom_key=None, mapbox_key=None, google_key=None, headless=True):
        self.tomtom_key = tomtom_key
        self.mapbox_key = mapbox_key
        self.google_key = google_key
        
        # API endpoints
        self.tomtom_base = "https://api.tomtom.com/search/2"
        self.mapbox_base = "https://api.mapbox.com"
        self.google_base = "https://maps.googleapis.com/maps/api/place"
        
        # Usage tracker
        self.tracker = UsageTracker()
        
        # Google Maps scraper (fallback)
        # Set headless=False to see browser, slow_mo=100 to slow down for debugging
        self.scraper = GoogleMapsScraperPlaywright(headless=headless, slow_mo=50)
        
        # Statistics
        self.stats = {
            'tomtom_calls': 0,
            'mapbox_calls': 0,
            'google_calls': 0,
            'scraper_items': 0,
            'total_cost': 0.0
        }
    
    async def search_businesses(self, keyword, location, max_results=100, min_rating=None):
        """
        Smart search that automatically selects best data source:
        Priority: Free tier APIs > Scraper (if APIs exhausted or not provided)
        """
        print(f"\n{'='*70}")
        print(f"🔍 SMART HYBRID SEARCH: {keyword} near {location}")
        print(f"{'='*70}\n")
        
        # Show free tier status
        self._print_free_tier_status()
        
        businesses = []
        
        # Phase 1: Geocoding (use Mapbox if available and within free tier)
        lat, lng = await self._smart_geocode(location)
        
        # Phase 2: Primary search - use best available option
        print(f"\n📍 Phase 1: Primary Search (Target: {max_results} results)")
        print("-" * 70)
        
        # Try TomTom first (50k free daily, cheapest paid option)
        if self.tomtom_key and self.tracker.can_use('tomtom', 1):
            print("  🎯 Using TomTom API (50k free/day)")
            tomtom_results = self._tomtom_search(keyword, lat, lng, max_results)
            businesses.extend(tomtom_results)
            self.tracker.record_usage('tomtom', 1)
            self.stats['tomtom_calls'] += 1
        
        # If we need more results, try Mapbox
        if len(businesses) < max_results and self.mapbox_key and self.tracker.can_use('mapbox', 1):
            needed = max_results - len(businesses)
            print(f"  🎯 Using Mapbox API (100k free/month) - need {needed} more")
            mapbox_results = self._mapbox_search(keyword, lat, lng, needed)
            businesses.extend(mapbox_results)
            self.tracker.record_usage('mapbox', 1)
            self.stats['mapbox_calls'] += 1
        
        # Phase 3: If still need results, use scraper as fallback
        if len(businesses) < max_results:
            needed = max_results - len(businesses)
            print(f"\n🌐 Phase 2: Scraper Fallback (FREE) - need {needed} more")
            print("-" * 70)
            
            if not self.tomtom_key and not self.mapbox_key:
                print("  ⚠️  No API keys provided - using scraper only")
            elif not self.tracker.can_use('tomtom', 1) and not self.tracker.can_use('mapbox', 1):
                print("  ⚠️  Free tier limits reached - using scraper")
            
            try:
                scraped = await self.scraper.scrape_google_maps(keyword, location, needed)
                businesses.extend(scraped)
                self.stats['scraper_items'] += len(scraped)
            except Exception as e:
                print(f"  ❌ Scraper failed: {str(e)[:100]}")
                print(f"  💡 Continuing with {len(businesses)} results from APIs")
        
        # Return early if we have no results
        if len(businesses) == 0:
            print(f"\n⚠️  No results found. Try:")
            print(f"   • Different search terms")
            print(f"   • Broader location (e.g., 'Seattle' instead of 'Seattle, WA')")
            print(f"   • Check API keys are valid")
            self._print_summary(businesses)
            return businesses
        
        # Phase 4: Enrich with Google API if available and needed
        # if self.google_key and min_rating or self._needs_enrichment(businesses):
        #     businesses = await self._smart_enrich(businesses, min_rating)
        
        # Deduplicate
        # businesses = self._deduplicate(businesses)
        
        # Apply filters
        # if min_rating:
        #     businesses = [b for b in businesses if self._check_rating(b, min_rating)]
        
        # Print summary
        self._print_summary(businesses[:max_results])
        if not max_results:
            return businesses
        return businesses[:max_results]
    async def _smart_geocode(self, location):
        """Smart geocoding - use free tier or fallback"""
        print("🌍 Geocoding location...")
        
        # Try Mapbox first (100k free/month)
        if self.mapbox_key and self.tracker.can_use('mapbox', 1):
            print("  🎯 Using Mapbox Geocoding (100k free/month)")
            coords = self._mapbox_geocode(location)
            if coords[0] is not None:  # Only record if actually got coordinates
                self.tracker.record_usage('mapbox', 1)
                self.stats['mapbox_calls'] += 1
                return coords
        
        # Try Google if Mapbox unavailable
        if self.google_key and self.tracker.can_use('google', 1):
            print("  🎯 Using Google Geocoding (10k free/month)")
            coords = self._google_geocode(location)
            if coords[0] is not None:  # Only record if actually got coordinates
                self.tracker.record_usage('google', 1)
                self.stats['google_calls'] += 1
                self.stats['total_cost'] += 0.005
                return coords
        
        print("  ⚠️  No geocoding API available, using approximate coordinates")
        return (0, 0)
    async def _smart_geocode_deprecated(self, location):
        """Smart geocoding - use free tier or fallback"""
        print("🌍 Geocoding location...")
        
        # Try Mapbox first (100k free/month)
        if self.mapbox_key and self.tracker.can_use('mapbox', 1):
            print("  🎯 Using Mapbox Geocoding (100k free/month)")
            coords = self._mapbox_geocode(location)
            if coords[0]:
                self.tracker.record_usage('mapbox', 1)
                self.stats['mapbox_calls'] += 1
                return coords
        
        # Try Google if Mapbox unavailable
        if self.google_key and self.tracker.can_use('google', 1):
            print("  🎯 Using Google Geocoding (10k free/month)")
            coords = self._google_geocode(location)
            if coords[0]:
                self.tracker.record_usage('google', 1)
                self.stats['google_calls'] += 1
                self.stats['total_cost'] += 0.005
                return coords
        
        print("  ⚠️  No geocoding API available, using approximate coordinates")
        return (0, 0)
    def _mapbox_geocode(self, location):
        """Geocode using Mapbox"""
        if not self.mapbox_key or self.mapbox_key == "YOUR_MAPBOX_API_KEY":
            return (None, None)
        
        try:
            url = f"{self.mapbox_base}/geocoding/v5/mapbox.places/{location}.json"
            params = {'access_token': self.mapbox_key, 'limit': 1}
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Check if we got actual results (not an error)
                if data.get('features') and len(data['features']) > 0:
                    coords = data['features'][0]['geometry']['coordinates']
                    lng, lat = coords[0], coords[1]
                    print(f"  ✅ Location: ({lat:.4f}, {lng:.4f})")
                    return (lat, lng)
        except:
            pass
        return (None, None)
    def _mapbox_geocode_dep(self, location):
        """Geocode using Mapbox"""
        try:
            url = f"{self.mapbox_base}/geocoding/v5/mapbox.places/{location}.json"
            params = {'access_token': self.mapbox_key, 'limit': 1}
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('features'):
                    coords = data['features'][0]['geometry']['coordinates']
                    lng, lat = coords[0], coords[1]
                    print(f"  ✅ Location: ({lat:.4f}, {lng:.4f})")
                    return (lat, lng)
        except:
            pass
        return (None, None)
    
    def _google_geocode(self, location):
        """Geocode using Google"""
        if not self.google_key or self.google_key == "YOUR_GOOGLE_API_KEY":
            return (None, None)
        
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {'address': location, 'key': self.google_key}
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    loc = data['results'][0]['geometry']['location']
                    print(f"  ✅ Location: ({loc['lat']:.4f}, {loc['lng']:.4f})")
                    return (loc['lat'], loc['lng'])
        except:
            pass
        return (None, None)
    
    def _tomtom_search(self, keyword, lat, lng, limit):
        """Search using TomTom API"""
        results = []
        
        try:
            url = f"{self.tomtom_base}/poiSearch/{keyword}.json"
            params = {
                'key': self.tomtom_key,
                'lat': lat,
                'lon': lng,
                'radius': 50000,
                'limit': min(limit, 100),
                'language': 'en-US'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get('results', []):
                    poi = item.get('poi', {})
                    address = item.get('address', {})
                    
                    business = {
                        'name': poi.get('name', ''),
                        'source': 'TomTom API',
                        'data_method': 'api',
                        'address': address.get('freeformAddress', ''),
                        'phone': poi.get('phone', ''),
                        'website': poi.get('url', ''),
                        'category': ', '.join(poi.get('categories', [])),
                        'latitude': item.get('position', {}).get('lat', ''),
                        'longitude': item.get('position', {}).get('lon', ''),
                        'rating': '',
                        'reviews_count': '',
                        'price_level': '',
                        'hours': ''
                    }
                    results.append(business)
                
                print(f"  ✅ Found {len(results)} businesses")
                
                # Track cost (only if beyond free tier)
                if not self.tracker.can_use('tomtom', 0):
                    self.stats['total_cost'] += 0.0005
        except Exception as e:
            print(f"  ❌ TomTom error: {str(e)}")
        
        return results
    
    def _mapbox_search(self, keyword, lat, lng, limit):
        """Search using Mapbox"""
        results = []
        
        try:
            url = f"{self.mapbox_base}/geocoding/v5/mapbox.places/{keyword}.json"
            params = {
                'access_token': self.mapbox_key,
                'proximity': f"{lng},{lat}",
                'limit': min(limit, 10),
                'types': 'poi'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                for feature in data.get('features', []):
                    coords = feature['geometry']['coordinates']
                    properties = feature.get('properties', {})
                    
                    business = {
                        'name': feature.get('text', ''),
                        'source': 'Mapbox API',
                        'data_method': 'api',
                        'address': feature.get('place_name', ''),
                        'phone': properties.get('phone', ''),
                        'website': '',
                        'category': properties.get('category', ''),
                        'latitude': coords[1],
                        'longitude': coords[0],
                        'rating': '',
                        'reviews_count': '',
                        'price_level': '',
                        'hours': ''
                    }
                    results.append(business)
                
                print(f"  ✅ Found {len(results)} businesses")
                
                # Track cost
                if not self.tracker.can_use('mapbox', 0):
                    self.stats['total_cost'] += 0.002
        except Exception as e:
            print(f"  ❌ Mapbox error: {str(e)}")
        
        return results
    
    def _needs_enrichment(self, businesses):
        """Check if businesses need enrichment (missing ratings/reviews)"""
        if not self.google_key:
            return False
        if not businesses:
            return False
        
        missing_ratings = sum(1 for b in businesses if not b.get('rating'))
        return missing_ratings > len(businesses) * 0.5  # More than 50% missing
    
    async def _smart_enrich(self, businesses, min_rating):
        """Smart enrichment using Google API within free tier"""
        print(f"\n⭐ Phase 3: Enrichment (ratings & reviews)")
        print("-" * 70)
        
        if not self.google_key:
            print("  ⚠️  No Google API key - skipping enrichment")
            return businesses
        
        enriched = []
        google_remaining = self.tracker.get_remaining('google')
        max_enrich = min(20, google_remaining // 2)  # Use max 20 or half of remaining
        
        if google_remaining == 0:
            print("  ⚠️  Google API free tier exhausted - skipping enrichment")
            return businesses
        
        print(f"  🎯 Using Google Places API (within free tier: {google_remaining} remaining)")
        print(f"  📊 Enriching up to {max_enrich} businesses")
        
        enriched_count = 0
        
        for business in businesses:
            # Only enrich if missing key data
            if business.get('rating') and business.get('reviews_count'):
                enriched.append(business)
                continue
            
            if enriched_count >= max_enrich:
                enriched.append(business)
                continue
            
            # Find on Google
            google_data = self._find_google_place(
                business.get('name', ''),
                business.get('latitude', 0),
                business.get('longitude', 0)
            )
            
            if google_data:
                business.update({
                    'rating': google_data.get('rating', business.get('rating', '')),
                    'reviews_count': google_data.get('user_ratings_total', business.get('reviews_count', '')),
                    'price_level': google_data.get('price_level', business.get('price_level', '')),
                    'source': f"{business['source']} + Google"
                })
                enriched_count += 1
                self.tracker.record_usage('google', 2)  # Nearby + Details
                self.stats['google_calls'] += 2
            
            enriched.append(business)
            time.sleep(0.2)
        
        print(f"  ✅ Enriched {enriched_count} businesses")
        
        return enriched
    
    def _find_google_place(self, name, lat, lng):
        """Find place on Google"""
        try:
            # Nearby search
            url = f"{self.google_base}/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': 100,
                'keyword': name,
                'key': self.google_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    place = data['results'][0]
                    return {
                        'rating': place.get('rating'),
                        'user_ratings_total': place.get('user_ratings_total'),
                        'price_level': place.get('price_level')
                    }
        except:
            pass
        return None
    
    def _deduplicate(self, businesses):
        """Remove duplicates"""
        seen = set()
        unique = []
        
        for business in businesses:
            key = (business.get('name', '').lower().strip(), 
                   business.get('address', '').lower().strip()[:30])
            if key not in seen and key[0]:
                seen.add(key)
                unique.append(business)
        
        return unique
    
    def _check_rating(self, business, min_rating):
        """Check if business meets rating requirement"""
        rating = business.get('rating', '')
        if not rating:
            return False
        try:
            return float(rating) >= min_rating
        except:
            return False
    
    def _print_free_tier_status(self):
        """Print free tier usage status"""
        status = self.tracker.get_status()
        
        print("📊 FREE TIER STATUS:")
        print("-" * 70)
        
        for api, info in status.items():
            api_name = api.upper()
            used = info['used']
            remaining = info['remaining']
            limit = info['limit']
            period = info['period']
            
            percentage = (used / limit * 100) if limit > 0 else 0
            bar_length = 30
            filled = int(bar_length * used / limit) if limit > 0 else 0
            bar = '█' * filled + '░' * (bar_length - filled)
            
            print(f"  {api_name:8} [{bar}] {used:,}/{limit:,} ({percentage:.1f}%) - {period}")
        
        print("-" * 70)
    
    def _print_summary(self, businesses):
        """Print extraction summary"""
        print(f"\n{'='*70}")
        print("📊 EXTRACTION SUMMARY")
        print("=" * 70)
        print(f"Total businesses extracted: {len(businesses)}")
        print(f"\nData sources breakdown:")
        print(f"  TomTom API calls:     {self.stats['tomtom_calls']}")
        print(f"  Mapbox API calls:     {self.stats['mapbox_calls']}")
        print(f"  Google API calls:     {self.stats['google_calls']}")
        print(f"  Scraped items:        {self.stats['scraper_items']}")
        print(f"\nEstimated cost:         ${self.stats['total_cost']:.4f}")
        print("=" * 70)
    
    def save_to_csv(self, businesses, filename=None):
        """Save to CSV"""
        if not businesses:
            print("\n❌ No businesses to save")
            return
        
        if not filename:
            filename = f'businesses_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        fieldnames = list(businesses[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(businesses)
        
        print(f"\n✅ Data saved to {filename}")
        return filename
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.scraper.close_browser()


# Main execution
async def main():
    """
    Smart Hybrid Strategy:
    1. Uses all free tiers first (Google 10k, TomTom 50k, Mapbox 100k)
    2. Falls back to scraping when free tiers exhausted
    3. Falls back to scraping if API keys not provided
    4. Tracks usage across sessions
    """
    
    # API Keys - Replace with your actual keys or set to None
    TOMTOM_KEY = "YOUR_TOMTOM_API_KEY"  # Get from: https://developer.tomtom.com
    MAPBOX_KEY = "YOUR_MAPBOX_API_KEY"  # Get from: https://account.mapbox.com
    GOOGLE_KEY = "YOUR_GOOGLE_API_KEY"  # Get from: https://console.cloud.google.com
    
    # For testing without API keys (will use scraper only):
    # TOMTOM_KEY = None
    # MAPBOX_KEY = None
    # GOOGLE_KEY = None
    
    # Initialize extractor
    # Set headless=False to see the browser while scraping (useful for debugging)
    extractor = SmartHybridExtractor(TOMTOM_KEY, MAPBOX_KEY, GOOGLE_KEY, headless=False)
    
    # DEBUGGING OPTIONS:
    # Make it MUCH slower so you can see every action
    extractor.scraper.slow_mo = 500  # 500ms delay - you'll see each click clearly
    
    # Or make it faster once working
    # extractor.scraper.slow_mo = 50
    
    try:
        # Search parameters
        search_params = {
            'keyword': 'adult family homes',
            'location': 'Seattle, WA',
            'max_results': 50,
            'min_rating': 4.0  # Set to None to get all results
        }
        
        print("\n💡 TIP: If scraping fails, the script will still return API results!")
        print("💡 TIP: Set headless=False in the script to see browser for debugging")
        
        # Execute search
        businesses = await extractor.search_businesses(**search_params)
        
        if len(businesses) > 0:
            # Save results
            extractor.save_to_csv(businesses)
            
            # Print sample results
            print("\n📋 SAMPLE RESULTS (First 5):")
            print("=" * 70)
            for i, business in enumerate(businesses[:5], 1):
                print(f"\n{i}. {business.get('name', 'Unknown')}")
                print(f"   📍 Address: {business.get('address', 'N/A')}")
                print(f"   📞 Phone: {business.get('phone', 'N/A')}")
                print(f"   ⭐ Rating: {business.get('rating', 'N/A')} ({business.get('reviews_count', 'N/A')} reviews)")
                print(f"   🌐 Website: {business.get('website', 'N/A')}")
                print(f"   📊 Source: {business.get('source', 'N/A')}")
                print(f"   🔧 Method: {business.get('data_method', 'N/A')}")
            
            print("\n" + "=" * 70)
        else:
            print("\n" + "="*70)
            print("❌ NO RESULTS FOUND")
            print("="*70)
            print("\n💡 TROUBLESHOOTING:")
            print("   1. Verify your API keys are correct")
            print("   2. Try a simpler search term (e.g., 'coffee shop')")
            print("   3. Try a broader location (e.g., 'Seattle' instead of 'Seattle, WA')")
            print("   4. Check your internet connection")
            print("   5. If using scraper, try running with headless=False to see what's happening")
            print("\n📝 EXAMPLE WITH WORKING SEARCH:")
            print("   keyword='coffee shop'")
            print("   location='Seattle'")
        
    finally:
        # Cleanup
        await extractor.cleanup()


# Batch processing example
async def batch_search_multiple_locations():
    """
    Example: Search multiple cities and combine results
    """
    TOMTOM_KEY = "YOUR_TOMTOM_API_KEY"
    MAPBOX_KEY = "YOUR_MAPBOX_API_KEY"
    GOOGLE_KEY = "YOUR_GOOGLE_API_KEY"
    
    extractor = SmartHybridExtractor(TOMTOM_KEY, MAPBOX_KEY, GOOGLE_KEY)
    
    cities = [
        'Seattle, WA',
        'Portland, OR',
        'San Francisco, CA'
    ]
    
    all_businesses = []
    
    try:
        for city in cities:
            print(f"\n\n{'#'*70}")
            print(f"# Searching: {city}")
            print(f"{'#'*70}")
            
            businesses = await extractor.search_businesses(
                keyword='pizza restaurant',
                location=city,
                max_results=30,
                min_rating=4.0
            )
            
            # Add city tag to each business
            for business in businesses:
                business['search_city'] = city
            
            all_businesses.extend(businesses)
            
            # Small delay between cities
            await asyncio.sleep(2)
        
        # Save combined results
        filename = f'multi_city_search_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        extractor.save_to_csv(all_businesses, filename)
        
        print(f"\n\n{'='*70}")
        print(f"TOTAL RESULTS: {len(all_businesses)} businesses across {len(cities)} cities")
        print("=" * 70)
        
    finally:
        await extractor.cleanup()


# Advanced filtering example
async def advanced_search_with_filters():
    """
    Example: Advanced search with custom filters
    """
    TOMTOM_KEY = "YOUR_TOMTOM_API_KEY"
    MAPBOX_KEY = "YOUR_MAPBOX_API_KEY"
    GOOGLE_KEY = "YOUR_GOOGLE_API_KEY"
    
    extractor = SmartHybridExtractor(TOMTOM_KEY, MAPBOX_KEY, GOOGLE_KEY)
    
    try:
        # Get raw results
        businesses = await extractor.search_businesses(
            keyword='restaurant',
            location='New York, NY',
            max_results=100,
            min_rating=None  # Get all, filter later
        )
        
        # Advanced filtering
        filtered = []
        for business in businesses:
            # Must have rating
            if not business.get('rating'):
                continue
            
            rating = float(business['rating'])
            reviews = int(business.get('reviews_count', 0)) if business.get('reviews_count') else 0
            
            # Custom filters
            if (rating >= 4.5 and 
                reviews >= 100 and 
                business.get('phone') and 
                business.get('website')):
                filtered.append(business)
        
        print(f"\n📊 Filtered Results: {len(filtered)}/{len(businesses)} businesses")
        print("   Criteria: Rating ≥4.5, Reviews ≥100, Has phone & website")
        
        extractor.save_to_csv(filtered, 'filtered_restaurants.csv')
        
    finally:
        await extractor.cleanup()


# No API keys example - Pure scraper mode
async def scraper_only_mode():
    """
    Example: Use without any API keys (100% free, 100% scraping)
    WARNING: This violates Google's Terms of Service
    """
    print("\n⚠️  SCRAPER-ONLY MODE (No API keys required)")
    print("⚠️  WARNING: This violates Google's Terms of Service")
    print("⚠️  Use for educational/testing purposes only\n")
    
    # No API keys provided
    extractor = SmartHybridExtractor(
        tomtom_key=None,
        mapbox_key=None,
        google_key=None
    )
    
    try:
        businesses = await extractor.search_businesses(
            keyword='dentist',
            location='Austin, TX',
            max_results=20,
            min_rating=4.0
        )
        
        extractor.save_to_csv(businesses, 'scraped_dentists.csv')
        
        print(f"\n✅ Extracted {len(businesses)} businesses")
        print("💰 Total cost: $0.00 (Pure scraping)")
        
    finally:
        await extractor.cleanup()


# Check free tier status
def check_api_status():
    """
    Check remaining free tier calls without making any requests
    """
    tracker = UsageTracker()
    status = tracker.get_status()
    
    print("\n" + "="*70)
    print("📊 API FREE TIER STATUS")
    print("="*70)
    
    for api, info in status.items():
        print(f"\n{api.upper()}:")
        print(f"  Used:      {info['used']:,} calls")
        print(f"  Remaining: {info['remaining']:,} calls")
        print(f"  Limit:     {info['limit']:,} calls per {info['period']}")
        
        if info['remaining'] == 0:
            print(f"  ⚠️  FREE TIER EXHAUSTED - Will use scraper or incur costs")
        elif info['remaining'] < info['limit'] * 0.1:
            print(f"  ⚠️  LOW - {(info['used']/info['limit']*100):.1f}% used")
        else:
            print(f"  ✅ Available - {(info['remaining']/info['limit']*100):.1f}% remaining")
    
    print("\n" + "="*70)


# Reset usage tracking (use at start of new month/day)
def reset_usage_tracking():
    """
    Manually reset usage tracking
    Use this if you want to start fresh or if automatic reset fails
    """
    tracker = UsageTracker()
    
    for api in ['google', 'tomtom', 'mapbox']:
        tracker.usage[api] = {'count': 0, 'date': str(date.today())}
    
    tracker._save_usage()
    print("✅ Usage tracking reset for all APIs")


# Quick API-only mode (no scraping)
async def api_only_search():
    """
    Use ONLY APIs - no scraping (100% legal, no timeout issues)
    Perfect when scraping fails or for production use
    """
    print("\n" + "="*70)
    print("🔧 API-ONLY MODE (No scraping)")
    print("="*70)
    
    TOMTOM_KEY = "YOUR_TOMTOM_API_KEY"
    MAPBOX_KEY = "YOUR_MAPBOX_API_KEY"
    GOOGLE_KEY = "YOUR_GOOGLE_API_KEY"
    
    extractor = SmartHybridExtractor(TOMTOM_KEY, MAPBOX_KEY, GOOGLE_KEY)
    
    # Disable scraper
    extractor.scraper = None
    
    try:
        businesses = await extractor.search_businesses(
            keyword='restaurant',
            location='Seattle',
            max_results=100,
            min_rating=4.0
        )
        
        if businesses:
            extractor.save_to_csv(businesses, 'api_only_results.csv')
            print(f"\n✅ Extracted {len(businesses)} businesses using APIs only")
        else:
            print("\n⚠️  No results. Check your API keys.")
        
    finally:
        # No browser to cleanup
        pass


# Test mode - scrape just a few with extra debugging
async def test_scraper_only():
    """
    Test the scraper with maximum visibility
    Perfect for debugging - you'll see exactly what's happening
    """
    print("\n" + "="*70)
    print("🧪 TEST MODE - Scraper with Full Visibility")
    print("="*70)
    print("\n💡 Browser will open and you'll see:")
    print("   • Red borders around cards before clicking")
    print("   • Slow-motion actions (500ms delays)")
    print("   • Detailed step-by-step output")
    print("   • Only scraping 5 results for quick testing\n")
    MONGO_URI = "mongodb://whatsapp_gateway:dWAYRRHyPbkrErhA98@172.232.181.126:27017/whatsapp_gateway?tls=false"
    db = MongoDBHandler(MONGO_URI)
    # No API keys needed for testing
    extractor = SmartHybridExtractor(None, None, None, headless=False)
    
    # VERY slow for debugging
    extractor.scraper.slow_mo = 50
    
    try:
        businesses = await extractor.search_businesses(
            keyword='adult family homes',  # Simple search for testing
            location='Seattle',
            max_results=300, 
            min_rating=None
        )
        
        if businesses:
            db.save_businesses_batch(businesses)
            print(f"\n✅ TEST SUCCESSFUL - Extracted {len(businesses)} businesses")
            for i, b in enumerate(businesses, 1):
                print(f"\n{i}. {b.get('name')}")
                print(f"   Rating: {b.get('rating')} ({b.get('reviews_count')} reviews)")
                print(f"   Phone: {b.get('phone')}")
                print(f"   address: {b.get('address')}")
                print(f"   geo: {b.get('latitude')},{b.get('longitude')}")
                # print(f"   google_maps_url: {b.get('google_maps_url')}")
        else:
            print("\n⚠️ No results extracted - check the browser window for errors")
        
        # Keep browser open for inspection
        print("\n⏸️  Browser will stay open for 30 seconds so you can inspect...")
        await asyncio.sleep(30)
        
    finally:
        await extractor.cleanup()


import requests
import csv
import time
from datetime import datetime, date
import re
from typing import List, Dict, Optional
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import json
import os
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

# Washington State Cities (Major cities and counties)
WA_CITIES = [
    # Major cities
    'Seattle', 'Spokane', 'Tacoma', 'Vancouver', 'Bellevue', 'Kent', 'Everett',
    'Renton', 'Spokane Valley', 'Federal Way', 'Yakima', 'Kirkland', 'Bellingham',
    'Kennewick', 'Auburn', 'Pasco', 'Marysville', 'Lakewood', 'Redmond', 'Shoreline',
    'Richland', 'Sammamish', 'Burien', 'Olympia', 'Lacey', 'Edmonds', 'Bremerton',
    'Puyallup', 'Lynnwood', 'Bothell', 'Longview', 'Pullman', 'Wenatchee', 'Mount Vernon',
    'University Place', 'Walla Walla', 'SeaTac', 'Maple Valley', 'Lake Stevens',
    'Mercer Island', 'Issaquah', 'Covington', 'Tukwila', 'Des Moines', 'Woodinville',
    
    # Additional cities
    'Anacortes', 'Arlington', 'Battle Ground', 'Bonney Lake', 'Bothell', 'Bremerton',
    'Camas', 'Centralia', 'Chehalis', 'Cheney', 'Clarkston', 'College Place', 'Cottage Grove',
    'East Wenatchee', 'Ellensburg', 'Enumclaw', 'Ferndale', 'Fife', 'Gig Harbor',
    'Grandview', 'Hoquiam', 'Kelso', 'Lake Forest Park', 'Liberty Lake', 'Lynden',
    'Moses Lake', 'Mount Vernon', 'Mountlake Terrace', 'Mukilteo', 'Newcastle',
    'Oak Harbor', 'Orchards', 'Othello', 'Port Angeles', 'Port Orchard', 'Port Townsend',
    'Poulsbo', 'Prosser', 'Pullman', 'Renton', 'Ridgefield', 'Sammamish', 'Sedro-Woolley',
    'Selah', 'Shelton', 'Silverdale', 'Snohomish', 'Snoqualmie', 'Sunnyside', 'Toppenish',
    'Tumwater', 'Union Gap', 'Walla Walla', 'Washougal', 'West Richland', 'White Center',
    'Yelm'
]


class MongoDBHandler:
    """Handle MongoDB operations"""
    
    def __init__(self, connection_string):
        self.client = MongoClient(connection_string)
        self.db = self.client.get_database()
        self.collection = self.db['adult_family_homes']
        
        # Create indexes
        self.collection.create_index([('name', ASCENDING), ('address', ASCENDING)], unique=True)
        self.collection.create_index([('city', ASCENDING)])
        self.collection.create_index([('rating', ASCENDING)])
        self.collection.create_index([('created_at', ASCENDING)])
        self.collection.create_index([('last_synced', ASCENDING)])
        
    def save_business(self, business_data):
        """Save a single business to MongoDB"""
        try:
            current_time = datetime.utcnow()
            
            # Check if document exists
            existing = self.collection.find_one({
                'name': business_data['name'], 
                'address': business_data['address']
            })
            
            if existing:
                # Update existing document - preserve created_at, update last_synced
                business_data['last_synced'] = current_time
                business_data['created_at'] = existing.get('created_at', current_time)
                
                self.collection.update_one(
                    {'name': business_data['name'], 'address': business_data['address']},
                    {'$set': business_data}
                )
                return False  # Not a new document
            else:
                # New document - set both created_at and last_synced
                business_data['created_at'] = current_time
                business_data['last_synced'] = current_time
                
                self.collection.insert_one(business_data)
                return True  # New document
                
        except DuplicateKeyError:
            return False
        except Exception as e:
            print(f"    MongoDB error: {str(e)[:100]}")
            return False
    
    def save_businesses_batch(self, businesses):
        """Save multiple businesses"""
        saved = 0
        updated = 0
        
        for business in businesses:
            if self.save_business(business):
                saved += 1
            else:
                updated += 1
        
        return saved, updated
    
    def get_stats(self):
        """Get collection statistics"""
        total = self.collection.count_documents({})
        
        # Get newest and oldest documents
        newest = self.collection.find_one(sort=[('created_at', -1)])
        oldest = self.collection.find_one(sort=[('created_at', 1)])
        
        # Get recently synced
        recently_synced = self.collection.count_documents({
            'last_synced': {'$gte': datetime.utcnow() - timedelta(hours=24)}
        })
        
        by_city = list(self.collection.aggregate([
            {'$group': {'_id': '$city', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]))
        
        return {
            'total': total,
            'by_city': by_city,
            'newest': newest.get('created_at') if newest else None,
            'oldest': oldest.get('created_at') if oldest else None,
            'synced_24h': recently_synced
        }
    
    def close(self):
        """Close MongoDB connection"""
        self.client.close()
class GoogleMapsScraperPlaywright:
    """Google Maps scraper using Playwright"""
    
    def __init__(self, headless=True, slow_mo=0):
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser = None
        self.context = None
        self.page = None
        
    async def init_browser(self):
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--start-maximized']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(90000)
        
    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
    
    async def scrape_google_maps(self, search_query, location, max_results=100):
        """Scrape Google Maps search results with infinite scroll and images"""
        if not self.page:
            await self.init_browser()
        
        businesses = []
        
        import urllib.parse
        encoded_query = urllib.parse.quote(f"{search_query} in {location}")
        search_url = f"https://www.google.com/maps/search/{encoded_query}"
        
        try:
            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(5)
            
            await self.page.wait_for_selector('div.Nv2PK', timeout=20000)
            
            # Infinite scroll to load all results
            results_panel = await self.page.query_selector('div[role="feed"]')
            
            if results_panel:
                previous_count = 0
                no_new_results_count = 0
                scroll_attempts = 0
                max_scroll_attempts = 30
                
                while scroll_attempts < max_scroll_attempts:
                    await results_panel.evaluate('el => el.scrollTop = el.scrollHeight')
                    await asyncio.sleep(2)
                    
                    business_cards = await self.page.query_selector_all('div.Nv2PK')
                    current_count = len(business_cards)
                    
                    if current_count == previous_count:
                        no_new_results_count += 1
                        if no_new_results_count >= 3:
                            break
                    else:
                        no_new_results_count = 0
                    
                    previous_count = current_count
                    scroll_attempts += 1
                    
                    if current_count >= max_results * 2:
                        break
            
            # PHASE 1: Collect all business names from cards
            print("  📝 Collecting business names...")
            business_cards = await self.page.query_selector_all('div.Nv2PK')
            business_names = []
            
            for card in business_cards:
                try:
                    name_el = await card.query_selector('div.qBF1Pd, div.fontHeadlineSmall')
                    if name_el:
                        name = (await name_el.inner_text()).strip()
                        if ' - Adult Family Homes' not in name and 'directory' not in name.lower():
                            business_names.append(name)
                except:
                    continue
            
            print(f"  📋 Found {len(business_names)} unique businesses")
            
            # PHASE 2: Process each business by finding its card by name
            scraped_names = set()
            successful_details = 0
            failed_details = 0
            
            for business_name in business_names[:max_results]:
                if business_name in scraped_names:
                    continue
                
                try:
                    # Navigate back to search
                    await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(2)
                    await self.page.wait_for_selector('div.Nv2PK', timeout=10000)
                    
                    # Find the card with this specific name
                    card_found = False
                    # bJzME Hu9e2e tTVLSc
                    business_cards = await self.page.query_selector_all('div.Nv2PK')
                    
                    for card in business_cards:
                        try:
                            name_el = await card.query_selector('div.qBF1Pd, div.fontHeadlineSmall')
                            if not name_el:
                                continue
                            
                            card_name = (await name_el.inner_text()).strip()
                            
                            if card_name == business_name:
                                card_found = True
                                
                                # Get basic card data
                                image_url = ''
                                rating = ''
                                reviews_count = ''
                                
                                try:
                                    img_el = await card.query_selector('img.DaSXdd, img.loaded')
                                    if img_el:
                                        img_src = await img_el.get_attribute('src')
                                        if img_src and img_src.startswith('http'):
                                            image_url = img_src
                                except:
                                    pass
                                
                                try:
                                    rating_el = await card.query_selector('span.MW4etd')
                                    if rating_el:
                                        rating = (await rating_el.inner_text()).strip()
                                except:
                                    pass
                                
                                try:
                                    reviews_el = await card.query_selector('span.UY7F9')
                                    if reviews_el:
                                        reviews_text = await reviews_el.inner_text()
                                        reviews_count = re.sub(r'[^\d]', '', reviews_text)
                                except:
                                    pass
                                
                                # Scroll and click
                                link = await card.query_selector('a.hfpxzc')
                                if link:
                                    await card.evaluate('el => el.scrollIntoView({block: "center"})')
                                    await asyncio.sleep(0.5)
                                    
                                    old_url = self.page.url
                                    
                                    try:
                                        await link.click(force=True)
                                        
                                        # Wait for URL change
                                        url_changed = False
                                        for _ in range(10):
                                            await asyncio.sleep(0.5)
                                            if self.page.url != old_url:
                                                url_changed = True
                                                break
                                        
                                        if url_changed:
                                            await asyncio.sleep(2)
                                            details = await self._extract_business_details()
                                            
                                            if details:
                                                business_data = details
                                                business_data['city'] = location
                                                business_data['source'] = 'Google Maps (Scraped)'
                                                business_data['data_method'] = 'scraper'
                                                
                                                if not business_data.get('rating'):
                                                    business_data['rating'] = rating
                                                if not business_data.get('reviews_count'):
                                                    business_data['reviews_count'] = reviews_count
                                                if not business_data.get('image_url'):
                                                    business_data['image_url'] = image_url
                                                
                                                successful_details += 1
                                            else:
                                                business_data = self._create_card_only_entry(business_name, location, image_url, rating, reviews_count)
                                                failed_details += 1
                                        else:
                                            business_data = self._create_card_only_entry(business_name, location, image_url, rating, reviews_count)
                                            failed_details += 1
                                    
                                    except Exception as e:
                                        business_data = self._create_card_only_entry(business_name, location, image_url, rating, reviews_count)
                                        failed_details += 1
                                else:
                                    business_data = self._create_card_only_entry(business_name, location, image_url, rating, reviews_count)
                                    failed_details += 1
                                
                                scraped_names.add(business_name)
                                businesses.append(business_data)
                                
                                status = "Full details" if business_data.get('phone') or business_data.get('address') else "Card only"
                                print(f"  ✅ {len(businesses)}: {business_name[:50]} - {status}")
                                
                                break
                        except:
                            continue
                    
                    if not card_found:
                        print(f"  ⚠️  Could not find card for: {business_name[:50]}")
                    
                except Exception as e:
                    print(f"  ❌ Error processing {business_name[:30]}: {str(e)[:50]}")
                    continue
            
            print(f"\n  ✅ Total: {len(businesses)} | Full details: {successful_details} | Card only: {failed_details}")
            
        except Exception as e:
            print(f"    Scraping error: {str(e)[:100]}")
        
        return businesses
    async def _extract_business_details(self):
        """Extract comprehensive business information including image"""
        try:
            await self.page.wait_for_selector('div.fontHeadlineSmall, h1', timeout=4000)
        except:
            return None
        
        try:
            data = {}
            
            # Name
            name_selectors = ['div.fontHeadlineSmall', 'h1.DUwDvf', 'div.qBF1Pd', 'h1']
            name_el = None
            for selector in name_selectors:
                name_el = await self.page.query_selector(selector)
                if name_el:
                    break
            
            if name_el:
                data['name'] = (await name_el.inner_text()).strip()
            else:
                return None
            
            # Image
            data['image_url'] = ''
            try:
                img_selectors = [
                    'button[aria-label*="Photo"] img',
                    'img.DaSXdd',
                    'div.RZ66Rb img',
                    'img[src*="googleusercontent"]'
                ]
                
                for selector in img_selectors:
                    img_el = await self.page.query_selector(selector)
                    if img_el:
                        img_src = await img_el.get_attribute('src')
                        if img_src and 'googleusercontent' in img_src:
                            if '=w' in img_src:
                                img_src = re.sub(r'=w\d+-h\d+', '=w800-h600', img_src)
                            data['image_url'] = img_src
                            break
            except:
                pass
            
            # Rating
            try:
                rating_el = await self.page.query_selector('span.MW4etd')
                data['rating'] = (await rating_el.inner_text()).strip() if rating_el else ''
            except:
                data['rating'] = ''
            
            # Reviews count
            try:
                reviews_el = await self.page.query_selector('span.UY7F9')
                if reviews_el:
                    reviews_text = await reviews_el.inner_text()
                    data['reviews_count'] = re.sub(r'[^\d]', '', reviews_text)
                else:
                    data['reviews_count'] = ''
            except:
                data['reviews_count'] = ''
            
            # Address
            try:
                data['address'] = ''
                w4_divs = await self.page.query_selector_all('div.W4Efsd')
                for div in w4_divs:
                    text = await div.inner_text()
                    if any(x in text for x in ['St', 'Ave', 'Rd', 'Blvd', 'Dr', 'Ln']) and any(c.isdigit() for c in text):
                        data['address'] = text.split('\n')[0].strip()
                        break
            except:
                data['address'] = ''
            
            # Phone
            try:
                phone_el = await self.page.query_selector('span.UsdlK')
                data['phone'] = (await phone_el.inner_text()).strip() if phone_el else ''
            except:
                data['phone'] = ''
            
            # Website
            try:
                website_el = await self.page.query_selector('a[data-value="Website"]')
                data['website'] = await website_el.get_attribute('href') if website_el else ''
            except:
                data['website'] = ''
            
            # Category
            try:
                data['category'] = ''
                w4_divs = await self.page.query_selector_all('div.W4Efsd span')
                for span in w4_divs[:3]:
                    text = await span.inner_text()
                    if 5 < len(text) < 50 and not any(x in text for x in ['St', 'Ave', '·', '(', 'Open', 'Closed']):
                        data['category'] = text.strip()
                        break
            except:
                data['category'] = ''
            
            data['hours'] = ''
            data['price_level'] = ''
            
            # URL and coordinates
            data['google_maps_url'] = self.page.url
            coords = self._extract_coordinates_from_url(self.page.url)
            data['latitude'] = coords[0] if coords else ''
            data['longitude'] = coords[1] if coords else ''
            
            return data
            
        except Exception as e:
            return None
    
    def _extract_coordinates_from_url(self, url):
        """Extract lat/lng from Google Maps URL"""
        try:
            pattern = r'@(-?\d+\.\d+),(-?\d+\.\d+)'
            match = re.search(pattern, url)
            if match:
                return (float(match.group(1)), float(match.group(2)))
        except:
            pass
        return None


async def scrape_all_wa_cities():
    """Scrape adult family homes from all WA cities and save to MongoDB"""
    
    # MongoDB connection
    MONGO_URI = "mongodb://whatsapp_gateway:dWAYRRHyPbkrErhA98@172.232.181.126:27017/whatsapp_gateway?tls=false"
    db = MongoDBHandler(MONGO_URI)
    
    # Initialize scraper
    scraper = GoogleMapsScraperPlaywright(headless=True, slow_mo=50)
    
    total_scraped = 0
    total_saved = 0
    total_duplicates = 0
    
    try:
        print(f"\n{'='*80}")
        print(f"SCRAPING ADULT FAMILY HOMES ACROSS WASHINGTON STATE")
        print(f"{'='*80}")
        print(f"Total cities: {len(WA_CITIES)}")
        print(f"MongoDB: Connected")
        print(f"{'='*80}\n")
        
        for idx, city in enumerate(WA_CITIES, 1):
            print(f"\n[{idx}/{len(WA_CITIES)}] {city}, WA")
            print("-" * 80)
            
            try:
                # Scrape this city
                businesses = await scraper.scrape_google_maps(
                    search_query='adult family homes',
                    location=f'{city}, WA',
                    max_results=500
                )
                
                if businesses:
                    # Save to MongoDB
                    saved, duplicates = db.save_businesses_batch(businesses)
                    
                    total_scraped += len(businesses)
                    total_saved += saved
                    total_duplicates += duplicates
                    
                    print(f"Scraped: {len(businesses)} | Saved: {saved} | Duplicates: {duplicates}")
                else:
                    print(f"No results found for {city}")
                
                # Brief pause between cities
                await asyncio.sleep(3)
                
            except Exception as e:
                print(f"Error scraping {city}: {str(e)[:100]}")
                continue
        
        # Final statistics
        print(f"\n{'='*80}")
        print(f"SCRAPING COMPLETE")
        print(f"{'='*80}")
        print(f"Total scraped: {total_scraped}")
        print(f"Total saved: {total_saved}")
        print(f"Total duplicates: {total_duplicates}")
        
        stats = db.get_stats()
        print(f"\nMongoDB Statistics:")
        print(f"Total businesses in database: {stats['total']}")
        print(f"\nTop 10 cities by count:")
        for city_stat in stats['by_city'][:10]:
            print(f"  {city_stat['_id']}: {city_stat['count']}")
        
        print(f"\n{'='*80}")
        
    finally:
        await scraper.close_browser()
        db.close()



# Run the script
if __name__ == "__main__":
    """
    INSTALLATION:
    pip install requests playwright
    python -m playwright install chromium
    
    USAGE MODES:
    
    1. TEST MODE (recommended first):
       Uncomment: asyncio.run(test_scraper_only())
       → Super slow, visible, only 5 results
    
    2. Smart Hybrid (production):
       python script.py
       → Uses APIs first, scraper as fallback
    
    3. API-only (no scraping):
       Uncomment: asyncio.run(api_only_search())
       → 100% legal, no timeout issues
    """
    
    # Check API status before running
    # check_api_status()
    
    # CHOOSE ONE:
    # asyncio.run(scrape_all_wa_cities())
    # Option 0: TEST MODE - Start here to see clicks working!
    asyncio.run(test_scraper_only())
    # Option 1: Smart hybrid (APIs + scraper fallback)
    # asyncio.run(main())
    
    # Option 2: API-only (no scraping - uncomment to use)
    # asyncio.run(api_only_search())
    
    # Option 3: Scraper-only (uncomment to use)
    # asyncio.run(scraper_only_mode())
    
    # Option 4: Batch multiple cities (uncomment to use)
    # asyncio.run(batch_search_multiple_locations())
    
    # Option 5: Advanced filtering (uncomment to use)
    # asyncio.run(advanced_search_with_filters())