$(function () {

  /* Functions */

  var loadForm = function () {
    $.ajax({
      url: $(this).data("form"),
      type: 'get',
      dataType: 'json',
      beforeSend: function () {
        $("#submit").attr('disabled','disabled');
      },
      success: function (data) {
        $("#editModal .modal-content").html(data.html_form);
        $('.select2').css('width', '100%');
        $(".select2").select2();
      },
      complete: function() {
        $(".data").inputmask("dd/mm/yyyy");
        $(".cpf").inputmask("999.999.999-99");
        $(".cnpj").inputmask("99.999.999/9999-99");
        $(".cep").inputmask("99.999-999");
        $('.select2').css('width', '70%');
        $(".select2").select2();
        $("#submit").removeAttr('disabled');
        loadambiente();
      }
    });
  };

  var saveForm = function () {
    var form = $(this);
    $.ajax({
      url: form.attr("action"),
      data: form.serialize(),
      type: form.attr("method"),
      dataType: 'json',
      beforeSend: function () {
        $("#progress").show();
      },
      success: function (data) {
        if (data.form_is_valid) {
          $("#dataTables-example tbody").html(data.html_list);
          $("#editModal").modal("hide");
        }
        else {
          $("#editModal .modal-content").html(data.html_form);
        }
      },
     complete: function() {
        $("#progress").hide();
      }
    });
    return false;
  };


  /* Binding */

  // Create book
  $(".js-create").click(loadForm);
  $("#editModal").on("submit", ".js-create-form", saveForm);

  // Update book
  $("#dataTables-example").on("click", ".js-update", loadForm);
  $("#editModal").on("submit", ".js-update-form", saveForm);


});