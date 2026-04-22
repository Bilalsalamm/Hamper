class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('session_cart')
        if not cart:
            cart = self.session['session_cart'] = {}
        self.cart = cart

    def add(self, hamper):
        hamper_id = str(hamper.id)
        if hamper_id not in self.cart:
            self.cart[hamper_id] = {
                'name': hamper.name,
                'price': str(hamper.price),
                'quantity': 1,
                'image': hamper.image.url if hamper.image else '',
                'description': hamper.description[:100]  # Store first 100 chars
            }
        else:
            self.cart[hamper_id]['quantity'] += 1
        self.session.modified = True

    def update_quantity(self, hamper_id, quantity):
        hamper_id = str(hamper_id)
        if hamper_id in self.cart:
            if quantity > 0:
                self.cart[hamper_id]['quantity'] = quantity
            else:
                del self.cart[hamper_id]
            self.session.modified = True

    def remove(self, hamper_id):
        hamper_id = str(hamper_id)
        if hamper_id in self.cart:
            del self.cart[hamper_id]
            self.session.modified = True

    def get_total(self):
        return sum(float(item['price']) * item['quantity'] for item in self.cart.values())

    def get_total_items(self):
        return sum(item['quantity'] for item in self.cart.values())