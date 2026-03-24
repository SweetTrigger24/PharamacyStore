from django.shortcuts import render, get_object_or_404, redirect
from .models import Product, Category, Customer, Cart, CartItem, Order, OrderItem, Inventory
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.contrib import messages
from django.db.models.functions import TruncDate, Coalesce
import uuid 

def home(request):
    return render(request, 'customer/trangchu.html')

def intro(request):
    return render(request, 'customer/gioithieu.html')

def opening(request):
    return render(request, 'customer/khaitruongwebsite.html')

def product_list(request):
    return render(request, 'customer/danhsachsanpham.html')

def product_detail(request, product_id):
    return render(request, 'customer/chitietsanpham.html')

@login_required
def cart(request):
    customer = request.user.customer
    cart = get_customer_cart(customer)
    items = cart.items.select_related('product').all()

    return render(request, 'customer/giohang.html', {
        'cart': cart,
        'items': items
    })

def checkout(request):
    return render(request, 'customer/dathang.html')

def profile(request):
    return render(request, 'customer/thongtincanhan.html')

def dashboard(request):
    return render(request, 'admin_panel/index.html')

def admin_categories(request):
    return render(request, 'admin_panel/danhmuc.html')

def admin_products(request):
    return render(request, 'admin_panel/sanpham.html')

def admin_inventory(request):
    return render(request, 'admin_panel/tonkho.html')

def admin_customers(request):
    return render(request, 'admin_panel/khachhang.html')

def admin_orders(request):
    return render(request, 'admin_panel/donhang.html')

def admin_statistics(request):
    return render(request, 'admin_panel/thongke.html')

def get_customer_cart(customer):
    cart, created = Cart.objects.get_or_create(customer=customer)
    return cart

def product_list(request):
    products = Product.objects.all()
    categories = Category.objects.all()

    category_id = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    if category_id:
        products = products.filter(category_id=category_id)

    if min_price:
        products = products.filter(price__gte=min_price)

    if max_price:
        products = products.filter(price__lte=max_price)

    return render(request, 'customer/danhsachsanpham.html', {
        'products': products,
        'categories': categories,
    })

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    inventory = Inventory.objects.filter(product=product).first()
    stock_quantity = inventory.quantity if inventory else 0

    stock_error_popup = request.session.pop('stock_error_popup', None)

    return render(request, 'customer/chitietsanpham.html', {
        'product': product,
        'inventory': inventory,
        'stock_quantity': stock_quantity,
        'stock_error_popup': stock_error_popup,
    })

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')

        if password != confirm_password:
            return redirect('home')

        if User.objects.filter(username=username).exists():
            return redirect('home')

        user = User.objects.create_user(username=username, password=password)

        customer = Customer.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            address=''
        )

        Cart.objects.get_or_create(customer=customer)

        return redirect('home')

    return redirect('home')

def logout_view(request):
    logout(request)
    return redirect('home')

def add_to_cart(request, product_id):
    if not request.user.is_authenticated:
        return redirect('home')

    product = get_object_or_404(Product, id=product_id)
    customer = request.user.customer
    cart = get_customer_cart(customer)

    quantity = int(request.POST.get('quantity', 1))
    if quantity < 1:
        quantity = 1

    item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    if created:
        item.quantity = quantity
    else:
        item.quantity += quantity

    item.save()
    return redirect('cart')


def cart(request):
    if not request.user.is_authenticated:
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    customer = get_or_create_customer(request.user)
    cart = get_customer_cart(customer)
    items = cart.items.all()

    return render(request, 'customer/giohang.html', {
        'cart': cart,
        'items': items
    })

@login_required
def checkout(request):
    customer = request.user.customer
    cart = get_customer_cart(customer)
    items = cart.items.select_related('product').all()

    if not items.exists():
        messages.error(request, 'Giỏ hàng của bạn đang trống.')
        return redirect('cart')

    if request.method == 'POST':
        receiver_name = request.POST.get('receiver_name', '').strip()
        receiver_phone = request.POST.get('receiver_phone', '').strip()
        delivery_address = request.POST.get('delivery_address', '').strip()
        note = request.POST.get('note', '').strip()
        payment_method = request.POST.get('payment_method', '').strip()

        if not receiver_name or not receiver_phone or not delivery_address or not payment_method:
            messages.error(request, 'Vui lòng nhập đầy đủ thông tin bắt buộc và chọn phương thức thanh toán.')
            return render(request, 'customer/dathang.html', {
                'cart': cart,
                'items': items,
                'receiver_name': receiver_name,
                'receiver_phone': receiver_phone,
                'delivery_address': delivery_address,
                'note': note,
                'payment_method': payment_method,
            })

        # Kiểm tra tồn kho trước khi tạo đơn
        for item in items:
            inventory = Inventory.objects.filter(product=item.product).first()
            available_quantity = inventory.quantity if inventory else 0

            if item.quantity > available_quantity:
                return render(request, 'customer/dathang.html', {
                    'cart': cart,
                    'items': items,
                    'receiver_name': receiver_name,
                    'receiver_phone': receiver_phone,
                    'delivery_address': delivery_address,
                    'note': note,
                    'payment_method': payment_method,
                    'stock_error_popup': (
                        f'Sản phẩm "{item.product.name}" chỉ còn '
                        f'{available_quantity} {item.product.unit} trong kho.'
                    )
                })

        order = Order.objects.create(
            customer=customer,
            code='DH' + uuid.uuid4().hex[:8].upper(),
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            delivery_address=delivery_address,
            note=note,
            payment_method=payment_method,
            subtotal=cart.total_amount()
        )

        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.product.price
            )

            inventory = Inventory.objects.filter(product=item.product).first()
            if inventory:
                inventory.quantity -= item.quantity
                if inventory.quantity < 0:
                    inventory.quantity = 0
                inventory.save()

        cart.items.all().delete()

        # Dùng session popup thay vì messages.success
        request.session['order_success_popup'] = 'Đặt hàng thành công!'

        if payment_method == 'bank':
            return redirect('payment_info', order_id=order.id)

        return redirect('home')

    return render(request, 'customer/dathang.html', {
        'cart': cart,
        'items': items,
        'receiver_name': '',
        'receiver_phone': '',
        'delivery_address': '',
        'note': '',
        'payment_method': '',
    })

def profile(request):
    if not request.user.is_authenticated:
        return redirect('home')

    customer = request.user.customer

    if request.method == 'POST':
        customer.full_name = request.POST.get('full_name')
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address')

        if 'avatar' in request.FILES:
            customer.avatar = request.FILES['avatar']

        customer.save()
        return redirect('profile')

    return render(request, 'customer/thongtincanhan.html', {
        'customer': customer
    })
@login_required
def change_password_view(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')

        user = request.user
        if user.check_password(old_password):
            user.set_password(new_password)
            user.save()
            return redirect('home')

    return redirect('profile')

def is_admin(user):
    return user.is_staff

@login_required
@user_passes_test(is_admin)
def dashboard(request):
    return render(request, 'admin_panel/index.html')

@login_required
@user_passes_test(is_admin)
def admin_categories(request):
    categories = Category.objects.all()
    return render(request, 'admin_panel/danhmuc.html', {
        'categories': categories
    })

@login_required
@user_passes_test(is_admin)
def admin_products(request):
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        proid = request.POST.get('proid')
        name = request.POST.get('name')
        description = request.POST.get('description')
        unit = request.POST.get('unit')
        price = request.POST.get('price')
        image = request.FILES.get('image')

        category = Category.objects.get(id=category_id)

        Product.objects.create(
            category=category,
            proid=proid,
            name=name,
            description=description,
            unit=unit,
            price=price,
            image=image
        )

        return redirect('admin_products')

    products = Product.objects.select_related('category').all()
    categories = Category.objects.all()

    return render(request, 'admin_panel/sanpham.html', {
        'products': products,
        'categories': categories
    })

@login_required
@user_passes_test(is_admin)
def admin_inventory(request):
    inventories = Inventory.objects.select_related('product').all()
    return render(request, 'admin_panel/tonkho.html', {
        'inventories': inventories
    })

@login_required
@user_passes_test(is_admin)
def admin_customers(request):
    customers = Customer.objects.select_related('user').all()
    return render(request, 'admin_panel/khachhang.html', {
        'customers': customers
    })

@login_required
@user_passes_test(is_admin)
def admin_orders(request):
    orders = Order.objects.select_related('customer').all().order_by('-created_at')
    return render(request, 'admin_panel/donhang.html', {
        'orders': orders
    })

@login_required
@user_passes_test(is_admin)
def admin_statistics(request):
    orders = Order.objects.all()

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        orders = orders.filter(created_at__date__gte=start_date)

    if end_date:
        orders = orders.filter(created_at__date__lte=end_date)

    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('subtotal'))['total'] or 0

    return render(request, 'admin_panel/thongke.html', {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
    })

def is_admin(user):
    return user.is_staff

@login_required
@user_passes_test(is_admin)
def admin_products(request):
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        proid = request.POST.get('proid', '').strip()
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        unit = request.POST.get('unit', '').strip()
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        image = request.FILES.get('image')

        category = get_object_or_404(Category, id=category_id)

        product = Product.objects.create(
            category=category,
            proid=proid,
            name=name,
            description=description,
            unit=unit,
            price=price,
            image=image
        )

        Inventory.objects.create(
            product=product,
            quantity=quantity or 0
        )

        return redirect('admin_products')

    keyword = request.GET.get('q', '').strip()

    products = Product.objects.select_related('category').all().order_by('id')

    if keyword:
        products = products.filter(
            Q(name__icontains=keyword) |
            Q(proid__icontains=keyword)
        )

    categories = Category.objects.all()

    return render(request, 'admin_panel/sanpham.html', {
        'products': products,
        'categories': categories,
        'keyword': keyword,
    })

@login_required
@user_passes_test(is_admin)
def admin_product_update(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        product.proid = request.POST.get('proid', '').strip()
        product.name = request.POST.get('name', '').strip()
        product.description = request.POST.get('description', '').strip()
        product.unit = request.POST.get('unit', '').strip()
        product.price = request.POST.get('price', 0)

        if category_id:
            product.category = get_object_or_404(Category, id=category_id)

        if request.FILES.get('image'):
            product.image = request.FILES.get('image')

        product.save()
        return redirect('admin_products')

    return redirect('admin_products')

@login_required
@user_passes_test(is_admin)
def admin_product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product.delete()

    return redirect('admin_products')

@login_required
@user_passes_test(is_admin)
def admin_inventory(request):
    keyword = request.GET.get('q', '')
    inventories = Inventory.objects.select_related('product').all()

    if keyword:
        inventories = inventories.filter(product__name__icontains=keyword)

    return render(request, 'admin_panel/tonkho.html', {
        'inventories': inventories,
        'keyword': keyword,
    })

@login_required
@user_passes_test(is_admin)
def admin_inventory_update(request, inventory_id):
    inventory = get_object_or_404(Inventory.objects.select_related('product'), id=inventory_id)

    if request.method == 'POST':
        inventory.quantity = request.POST.get('quantity')
        inventory.save()
        return redirect('admin_inventory')

    return render(request, 'admin_panel/inventory_edit.html', {
        'inventory': inventory,
    })

@login_required
@user_passes_test(is_admin)
def admin_orders(request):
    keyword = request.GET.get('q', '')
    orders = Order.objects.select_related('customer').all().order_by('-created_at')

    if keyword:
        orders = orders.filter(code__icontains=keyword)

    return render(request, 'admin_panel/donhang.html', {
        'orders': orders,
        'keyword': keyword,
    })

@login_required
@user_passes_test(is_admin)
def admin_order_update(request, order_id):
    order = get_object_or_404(Order.objects.select_related('customer'), id=order_id)

    if request.method == 'POST':
        order.status = request.POST.get('status')
        order.note = request.POST.get('note')
        order.save()
        return redirect('admin_orders')

    return render(request, 'admin_panel/order_edit.html', {
        'order': order,
    })

@login_required
@user_passes_test(is_admin)
def admin_order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.delete()
    return redirect('admin_orders')

@login_required
@user_passes_test(is_admin)
def dashboard(request):
    total_revenue = Order.objects.aggregate(total=Sum('subtotal'))['total'] or 0
    total_orders = Order.objects.count()
    total_stock = Inventory.objects.aggregate(total=Sum('quantity'))['total'] or 0
    recent_orders = Order.objects.select_related('customer').all().order_by('-created_at')[:5]

    return render(request, 'admin_panel/index.html', {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_stock': total_stock,
        'recent_orders': recent_orders,
    })

@login_required
@user_passes_test(is_admin)
def admin_statistics(request):
    orders = Order.objects.all()

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        orders = orders.filter(created_at__date__gte=start_date)

    if end_date:
        orders = orders.filter(created_at__date__lte=end_date)

    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('subtotal'))['total'] or 0

    return render(request, 'admin_panel/thongke.html', {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'start_date': start_date,
        'end_date': end_date,
    })      

@login_required
def profile(request):
    customer = request.user.customer

    if request.method == 'POST':
        customer.full_name = request.POST.get('full_name')
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address')

        if request.FILES.get('avatar'):
            customer.avatar = request.FILES.get('avatar')

        customer.save()
        return redirect('profile')

    return render(request, 'customer/thongtincanhan.html', {
        'customer': customer
    })

@login_required
def change_password_view(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        user = request.user

        if not user.check_password(old_password):
            messages.error(request, 'Mật khẩu cũ không đúng')
            return redirect('profile')

        if new_password != confirm_password:
            messages.error(request, 'Mật khẩu nhập lại không khớp')
            return redirect('profile')

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)

        messages.success(request, 'Đổi mật khẩu thành công')
        return redirect('profile')

    return redirect('profile')

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')

        if password != confirm_password:
            return redirect('home')

        if User.objects.filter(username=username).exists():
            return redirect('home')

        user = User.objects.create_user(username=username, password=password)
        customer = Customer.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            address=''
        )
        Cart.objects.create(customer=customer)

        return redirect('home')

    return redirect('home')

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def update_cart_item(request, item_id):
    customer = request.user.customer
    cart = get_customer_cart(customer)

    item = get_object_or_404(CartItem, id=item_id, cart=cart)

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity <= 0:
            item.delete()
        else:
            item.quantity = quantity
            item.save()

    return redirect('cart')

def get_or_create_customer(user):
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            'full_name': user.username,
            'phone': '',
            'address': ''
        }
    )
    return customer

@login_required
def payment_info(request, order_id):
    customer = request.user.customer
    order = get_object_or_404(Order, id=order_id, customer=customer)

    first_item = order.items.select_related('product').first()
    transfer_content = f"{order.code} {order.receiver_phone}"

    return render(request, 'customer/payment_info.html', {
        'order': order,
        'first_item': first_item,
        'transfer_content': transfer_content,
    })

@login_required
def delete_cart_item(request, item_id):
    customer = request.user.customer
    cart = get_customer_cart(customer)

    item = get_object_or_404(CartItem, id=item_id, cart=cart)

    if request.method == 'POST':
        item.delete()

    return redirect('cart')

def is_admin(user):
    return user.is_staff


@login_required
@user_passes_test(is_admin)
def admin_categories(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if name:
            Category.objects.create(
                name=name,
                description=description
            )
        return redirect('admin_categories')

    keyword = request.GET.get('q', '').strip()

    categories = Category.objects.all().order_by('id')

    if keyword:
        if keyword.isdigit():
            categories = categories.filter(
                Q(name__icontains=keyword) | Q(id=int(keyword))
            )
        else:
            categories = categories.filter(name__icontains=keyword)

    return render(request, 'admin_panel/danhmuc.html', {
        'categories': categories,
        'keyword': keyword,
    })


@login_required
@user_passes_test(is_admin)
def admin_category_update(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        category.name = request.POST.get('name', '').strip()
        category.description = request.POST.get('description', '').strip()
        category.save()

    return redirect('admin_categories')


@login_required
@user_passes_test(is_admin)
def admin_category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        category.delete()

    return redirect('admin_categories')

@login_required
@user_passes_test(is_admin)
def admin_inventory(request):
    inventories = Inventory.objects.select_related('product').all().order_by('product__proid')
    return render(request, 'admin_panel/tonkho.html', {
        'inventories': inventories
    })


@login_required
@user_passes_test(is_admin)
def admin_inventory_update(request, inventory_id):
    inventory = get_object_or_404(Inventory.objects.select_related('product'), id=inventory_id)

    if request.method == 'POST':
        quantity = request.POST.get('quantity', '').strip()
        if quantity != '':
            inventory.quantity = quantity
            inventory.save()

    return redirect('admin_inventory')

@login_required
@user_passes_test(is_admin)
def admin_orders(request):
    orders = Order.objects.select_related('customer').all().order_by('-created_at')
    return render(request, 'admin_panel/donhang.html', {
        'orders': orders
    })

@login_required
@user_passes_test(is_admin)
def admin_order_update(request, order_id):
    order = get_object_or_404(Order.objects.select_related('customer'), id=order_id)

    if request.method == 'POST':
        order.status = request.POST.get('status', '').strip()
        order.note = request.POST.get('note', '').strip()
        order.save()

    return redirect('admin_orders')


@login_required
@user_passes_test(is_admin)
def admin_order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == 'POST':
        order.delete()

    return redirect('admin_orders')

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Customer

def is_admin(user):
    return user.is_staff


@login_required
@user_passes_test(is_admin)
def admin_customers(request):
    customers = Customer.objects.select_related('user').all().order_by('id')
    return render(request, 'admin_panel/khachhang.html', {
        'customers': customers
    })


@login_required
@user_passes_test(is_admin)
def admin_customer_update(request, customer_id):
    customer = get_object_or_404(Customer.objects.select_related('user'), id=customer_id)

    if request.method == 'POST':
        customer.full_name = request.POST.get('full_name', '').strip()
        customer.phone = request.POST.get('phone', '').strip()
        customer.address = request.POST.get('address', '').strip()

        if request.FILES.get('avatar'):
            customer.avatar = request.FILES.get('avatar')

        customer.save()

    return redirect('admin_customers')

@login_required
@user_passes_test(is_admin)
def admin_customer_delete(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        customer.delete()

    return redirect('admin_customers')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            if user.is_staff:
                return redirect('dashboard')

            return redirect('home')
        else:
            return render(request, 'customer/trangchu.html', {
                'login_error': 'Sai tài khoản hoặc mật khẩu'
            })

    return redirect('home')

@login_required
@user_passes_test(is_admin)
def admin_statistics(request):
    orders = Order.objects.select_related('customer').all().order_by('-created_at')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        orders = orders.filter(created_at__date__gte=start_date)

    if end_date:
        orders = orders.filter(created_at__date__lte=end_date)

    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('subtotal'))['total'] or 0

    return render(request, 'admin_panel/thongke.html', {
        'orders': orders,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'start_date': start_date,
        'end_date': end_date,
    })

@login_required
@user_passes_test(is_admin)
def admin_inventory(request):
    keyword = request.GET.get('q', '').strip()

    inventories = Inventory.objects.select_related('product').all().order_by('id')

    if keyword:
        inventories = inventories.filter(
            Q(product__name__icontains=keyword) |
            Q(product__proid__icontains=keyword)
        )

    return render(request, 'admin_panel/tonkho.html', {
        'inventories': inventories,
        'keyword': keyword,
    })

@login_required
@user_passes_test(is_admin)
def admin_customers(request):
    keyword = request.GET.get('q', '').strip()

    customers = Customer.objects.select_related('user').all().order_by('id')

    if keyword:
        query = (
            Q(user__username__icontains=keyword) |
            Q(full_name__icontains=keyword) |
            Q(phone__icontains=keyword)
        )

        if keyword.isdigit():
            query = query | Q(id=int(keyword))

        customers = customers.filter(query)

    return render(request, 'admin_panel/khachhang.html', {
        'customers': customers,
        'keyword': keyword,
    })

@login_required
@user_passes_test(is_admin)
def admin_orders(request):
    keyword = request.GET.get('q', '').strip()

    orders = Order.objects.select_related('customer').all().order_by('-created_at')

    if keyword:
        query = Q(code__icontains=keyword) | Q(customer__full_name__icontains=keyword)

        # Nếu bạn muốn tìm thêm theo order.id thật (số nguyên)
        if keyword.isdigit():
            query = query | Q(id=int(keyword))

        orders = orders.filter(query)

    return render(request, 'admin_panel/donhang.html', {
        'orders': orders,
        'keyword': keyword,
    })

def admin_orders(request):
    orders = (
        Order.objects
        .select_related('customer')
        .prefetch_related('items__product')
        .all()
        .order_by('-created_at')
    )
    return render(request, 'admin_panel/donhang.html', {
        'orders': orders
    })

@login_required
def change_password_view(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        user = request.user

        if not user.check_password(old_password):
            messages.error(request, 'Mật khẩu cũ không đúng')
            return redirect('profile')

        if new_password != confirm_password:
            messages.error(request, 'Mật khẩu nhập lại không khớp')
            return redirect('profile')

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)

        messages.success(request, 'Đổi mật khẩu thành công')
        return redirect('profile')

    return redirect('profile')

def product_list(request):
    keyword = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    price_range = request.GET.get('price_range', '').strip()

    products = Product.objects.select_related('category').all().order_by('-id')
    categories = Category.objects.all().order_by('name')

    if keyword:
        products = products.filter(
            Q(name__icontains=keyword) |
            Q(description__icontains=keyword)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if price_range == 'under_100':
        products = products.filter(price__lt=100000)
    elif price_range == '100_300':
        products = products.filter(price__gte=100000, price__lte=300000)
    elif price_range == '300_500':
        products = products.filter(price__gte=300000, price__lte=500000)
    elif price_range == 'over_500':
        products = products.filter(price__gt=500000)

    return render(request, 'customer/danhsachsanpham.html', {
        'products': products,
        'categories': categories,
        'keyword': keyword,
        'selected_category': category_id,
        'selected_price_range': price_range,
    })

def home(request):
    featured_products = (
        Product.objects
        .annotate(
            total_sold=Coalesce(
                Sum(
                    'orderitem__quantity',
                    filter=~Q(orderitem__order__status='cancelled')
                ),
                0
            )
        )
        .order_by('-total_sold', 'name')[:8]
    )

    order_success_popup = request.session.pop('order_success_popup', None)

    return render(request, 'customer/trangchu.html', {
        'featured_products': featured_products,
        'order_success_popup': order_success_popup,
    })

def add_to_cart(request, product_id):
    if not request.user.is_authenticated:
        return redirect('home')

    product = get_object_or_404(Product, id=product_id)
    customer = request.user.customer
    cart = get_customer_cart(customer)

    quantity = int(request.POST.get('quantity', 1))
    if quantity < 1:
        quantity = 1

    inventory = Inventory.objects.filter(product=product).first()
    stock_quantity = inventory.quantity if inventory else 0

    item = CartItem.objects.filter(cart=cart, product=product).first()
    current_quantity = item.quantity if item else 0
    new_quantity = current_quantity + quantity

    if new_quantity > stock_quantity:
        request.session['stock_error_popup'] = (
            f'Sản phẩm "{product.name}" chỉ còn {stock_quantity} {product.unit} trong kho.'
        )
        return redirect('product_detail', product_id=product.id)

    if item:
        item.quantity = new_quantity
        item.save()
    else:
        CartItem.objects.create(cart=cart, product=product, quantity=quantity)

    return redirect('cart')